import re

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from core.constants import PERSON_SKIP_PREFIXES
from registers.models import CompanySyncStatus
from .models import Company, Watchlist, SectorBenchmark, SearchHistory, PostalCodeArea
from .seat_matching import BUILDING, POSTAL_CODE, STREET
from .services.financial_analysis import (
    FinancialAnalysisService,
    _amount,
    _ratio_present,
    _sum_present,
)
from .services.nace import get_nace_section, get_nace_section_name, get_nace_division_name
from .services.risk_score import compute_risk_score, risk_score_for_company


#: The closed vocabulary `financialsState` answers with -- a token, not a
#: sentence. The words belong to the screen (`frontend/companySections.ts`
#: already owns every other "why this section is thin" note), and the
#: operator-facing reason stays on the admin page, where
#: `CompanySyncStatus.last_detail` is written for someone who can act on it.
FINANCIALS_STATE_READY = "ready"
FINANCIALS_STATE_NOT_FETCHED = "not_fetched"
FINANCIALS_STATE_BLOCKED = "blocked"
FINANCIALS_STATE_FAILED = "failed"
FINANCIALS_STATE_NOTHING_RECORDED = "nothing_recorded"


class CompanyListSerializer(serializers.ModelSerializer):
    legal_form_short = serializers.CharField(source='get_legal_form_short', read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'ico', 'ruz_id', 'nazov_UJ', 'mesto', 'ulica', 'psc',
            'pravna_forma', 'legal_form_short', 'datum_zalozenia',
            'tax_debt', 'debt_vszp', 'debt_soc_poist'
        ]


class WatchlistSerializer(serializers.ModelSerializer):
    ico = serializers.CharField(source='company.ico', read_only=True)
    name = serializers.CharField(source='company.nazov_UJ', read_only=True)
    status = serializers.SerializerMethodField()
    riskScore = serializers.SerializerMethodField()
    addedAt = serializers.DateTimeField(source='added_at', read_only=True)

    class Meta:
        model = Watchlist
        fields = ['id', 'ico', 'name', 'status', 'riskScore', 'addedAt']

    def get_status(self, obj):
        return 'Vymazaná' if obj.company.datum_zrusenia else 'Aktívna'

    def get_riskScore(self, obj):
        """The same score the company's own page shows.

        It used to read the three debts and nothing else, so a company in the
        Altman bankruptcy zone with no debt was 100/100 here and 80/100 on its
        page -- the list and the detail disagreeing about the same company,
        with nothing on either screen to suggest which one was wrong.
        """
        return risk_score_for_company(obj.company)['score']


class CompanyDetailSerializer(serializers.ModelSerializer):
    legal_form = serializers.CharField(source='get_legal_form_display', read_only=True)
    financials = serializers.SerializerMethodField()
    financialsState = serializers.SerializerMethodField()
    analysis = serializers.SerializerMethodField()
    riskScore = serializers.SerializerMethodField()
    benchmark = serializers.SerializerMethodField()
    executives = serializers.SerializerMethodField()
    connections = serializers.SerializerMethodField()
    orsr_profile = serializers.SerializerMethodField()
    ruz_portal_url = serializers.SerializerMethodField()
    ruz_statements = serializers.SerializerMethodField()
    ruz_annual_reports = serializers.SerializerMethodField()
    seatLocation = serializers.SerializerMethodField()

    class Meta:
        model = Company
        # Everything except the two raw ID lists, which are counts to every
        # consumer this project has and arrays of up to 372 integers on the
        # wire (measured: Tatra Asset Management holds 372 statement IDs, and
        # the detail response is already 42 kB). `fields = '__all__'` published
        # them because they are fields on the model, not because anything read
        # them -- the two counts below are what a section can actually use.
        exclude = ['id_uctovnych_zavierok', 'id_vyrocnych_sprav']

    def get_financialsState(self, obj):
        """Why the financial sections are empty, when they are.

        The page used to answer every one of these with "nie sú k dispozícii",
        which is one sentence for four different facts -- and a reader cannot
        tell from it whether waiting would help, or whether asking again is
        pointless. The sync engine already knows which one it is, so it is
        named here rather than collapsed again one layer further out.

        Deliberately coarse in one place: the registry answering "this company
        has no statements" and the registry answering with statements, none of
        which could be read, both store zero rows, and the only thing that
        separates them is the wording of `last_detail` -- a sentence written
        for an operator. Both are `nothing_recorded`, which is the part that is
        certainly true of both, and the exact reason is one click away on the
        admin Stav synchronizácie page.
        """
        if obj.financial_results.exists():
            return FINANCIALS_STATE_READY

        status = obj.sync_statuses.filter(
            source=CompanySyncStatus.SOURCE_FINANCIALS
        ).first()
        if status is None:
            return FINANCIALS_STATE_NOT_FETCHED
        if status.is_blocked:
            return FINANCIALS_STATE_BLOCKED
        if status.consecutive_failures > 0:
            return FINANCIALS_STATE_FAILED
        return FINANCIALS_STATE_NOTHING_RECORDED

    def get_seatLocation(self, obj):
        """The seat on the map at whatever precision we can honestly claim.

        Three levels, tried best first, and the order is the policy:

        1. **`building`** — the register's own address point for this house
           number, in `seat_lat`/`seat_lon`, matched offline by
           `match_seat_addresses`. `radiusM` is 0 and the map draws a bare point,
           because there is no uncertainty left to draw. Measured 2026-09-13:
           78,6 % of our rows.
        2. **`street`** — the centroid of the company's street, with `radiusM`
           being the 90th-percentile distance to that street's own points, so the
           circle is a measured spread rather than a constant. 6,9 %.
        3. **`postal_code`** — the `PostalCodeArea` circle, unchanged. 14,5 %.

        The two sources are deliberately *not* merged. `seat_*` and
        `PostalCodeArea` are computed at different times from different levels of
        the same register, so a single blended answer would be a claim with two
        independent ways to go stale and no way to say which one moved. The
        fallback is chosen once, here, and each level names itself.

        `None` is a real answer and means "we cannot place this seat at all", not
        "the company has no seat": 1,92 % of our rows carry a PSČ the MV SR
        address register does not list (post-office PSČ with no address point),
        plus three rows with no PSČ at all. The map is omitted for those rather
        than drawn from a guess.
        """
        if obj.seat_precision in (BUILDING, STREET) and obj.seat_lat is not None:
            return {
                'lat': obj.seat_lat,
                'lon': obj.seat_lon,
                # The column is nullable and `street` is never 0, so the `or 0`
                # only ever fires for a building -- which is the value it wants.
                'radiusM': obj.seat_radius_m or 0,
                'psc': obj.psc or '',
                'precision': obj.seat_precision,
            }

        psc = PostalCodeArea.normalize_psc(obj.psc)
        if not psc:
            return None
        area = PostalCodeArea.objects.filter(psc=psc).first()
        if area is None:
            return None
        return {
            'lat': area.lat,
            'lon': area.lon,
            'radiusM': area.radius_m,
            'psc': area.psc,
            'precision': POSTAL_CODE,
        }

    def get_financials(self, obj):
        """Year rows with absent figures as `None`, never as 0.

        Every field used to be `float(r.X or 0)`, which made "the statement did
        not carry this line" and "the line reads zero" the same value. They are
        not the same fact, and the difference is now common rather than rare: the
        write gate stores a balance sheet on its own, so a row may legitimately
        have `revenue` and `profit` unset. `None` is the only representation that
        survives to the screen as `—` instead of `0 €`.

        The two ratios are computed by the same expressions the sector medians
        are computed by (`companies/services/benchmarking.py`), on purpose: the
        benchmark prints them side by side, and a comparison between two
        different formulas is not a comparison. That means an absent input
        yields no ratio here too -- a company that filed a balance sheet with no
        liabilities line has an unknown debt ratio, not a debt-free one.
        """
        results = obj.financial_results.all().order_by('year')
        out = []
        for r in results:
            revenue = _amount(r.revenue)
            added_value = _amount(r.added_value)
            assets_total = _amount(r.assets_total)
            liabilities_total = _amount(r.liabilities_total)
            liabilities_accruals = _amount(r.liabilities_accruals)

            debt_ratio = _ratio_present(
                _sum_present(liabilities_total, liabilities_accruals), assets_total
            )
            gross_margin = _ratio_present(added_value, revenue)

            out.append({
                'year': r.year,
                'revenue': revenue,
                'profit': _amount(r.profit),
                # The after-tax row, which `profit` used to be mistaken for. A
                # row that has not been re-read since the two were split carries
                # no value here, and `None` -- a dash on the screen -- is the
                # honest answer for it.
                'profitAfterTax': _amount(r.profit_after_tax),
                'totalRevenue': _amount(r.total_revenue),
                'costs': _amount(r.costs),
                'incomeTax': _amount(r.income_tax),
                'incomeTaxPaid': _amount(r.income_tax_paid),
                'assetsTotal': assets_total,
                'assetsIntangible': _amount(r.assets_intangible),
                'assetsTangible': _amount(r.assets_tangible),
                'assetsFinancial': _amount(r.assets_financial),
                'assetsCurrent': _amount(r.assets_current),
                'assetsInventory': _amount(r.assets_inventory),
                'assetsReceivablesLong': _amount(r.assets_receivables_long),
                'assetsReceivablesShort': _amount(r.assets_receivables_short),
                'assetsFinancialShort': _amount(r.assets_financial_short),
                'assetsFinancialAccounts': _amount(r.assets_financial_accounts),
                'assetsAccruals': _amount(r.assets_accruals),
                'equity': _amount(r.equity),
                'equityBasic': _amount(r.equity_basic),
                'equityCapitalFunds': _amount(r.equity_capital_funds),
                'equityProfitFunds': _amount(r.equity_profit_funds),
                'equityRetained': _amount(r.equity_retained),
                'liabilitiesTotal': liabilities_total,
                'liabilitiesReserves': _amount(r.liabilities_reserves),
                'liabilitiesLong': _amount(r.liabilities_long),
                'liabilitiesShort': _amount(r.liabilities_short),
                'liabilitiesAccruals': liabilities_accruals,
                'addedValue': added_value,
                'debtRatio': debt_ratio,
                'grossMargin': gross_margin,
            })
        return out

    def _analysis_payload(self, obj):
        """`analysis`, computed once per object.

        `get_analysis` and `get_riskScore` both need it, and DRF calls method
        fields independently -- without this the service would walk the
        company's financial results twice for every request.
        """
        cache = getattr(self, '_analysis_by_pk', None)
        if cache is None:
            cache = self._analysis_by_pk = {}
        if obj.pk not in cache:
            results = list(obj.financial_results.all().order_by('year'))
            cache[obj.pk] = (
                FinancialAnalysisService.to_dict(
                    FinancialAnalysisService.analyze(results)
                )
                if results
                else None
            )
        return cache[obj.pk]

    def get_analysis(self, obj):
        return self._analysis_payload(obj)

    def get_riskScore(self, obj):
        """The one risk score -- see `services/risk_score.py`.

        Published here rather than derived in the client because the client's
        copy and this one disagreed: the same company was `distress` and 80/100
        on its page while the watchlist, reading debt alone, called it 100/100.
        """
        return compute_risk_score(obj, self._analysis_payload(obj))

    def get_benchmark(self, obj):
        """Return sector benchmark for the company's NACE section."""
        nace = obj.sk_NACE
        section = get_nace_section(nace)
        if not section:
            return None

        # Find the latest year with financial data for this company
        latest_fr = obj.financial_results.order_by('-year').first()
        target_year = latest_fr.year if latest_fr else None
        if target_year is None:
            return None

        try:
            bm = SectorBenchmark.objects.get(nace_section=section, year=target_year)
        except SectorBenchmark.DoesNotExist:
            return None

        return {
            'section': section,
            'sectionName': get_nace_section_name(nace),
            'divisionName': get_nace_division_name(nace),
            'naceCode': nace,
            'year': bm.year,
            'companyCount': bm.company_count,
            'medians': {
                'revenue': float(bm.median_revenue) if bm.median_revenue else None,
                'profit': float(bm.median_profit) if bm.median_profit else None,
                'assetsTotal': float(bm.median_assets_total) if bm.median_assets_total else None,
                'equity': float(bm.median_equity) if bm.median_equity else None,
                'roa': float(bm.median_roa) if bm.median_roa else None,
                'roe': float(bm.median_roe) if bm.median_roe else None,
                'ros': float(bm.median_ros) if bm.median_ros else None,
                'debtRatio': float(bm.median_debt_ratio) if bm.median_debt_ratio else None,
                'grossMargin': float(bm.median_gross_margin) if bm.median_gross_margin else None,
                'currentRatio': float(bm.median_current_ratio) if bm.median_current_ratio else None,
                'selfFinancingRatio': float(bm.median_self_financing_ratio) if bm.median_self_financing_ratio else None,
            },
        }

    def get_ruz_portal_url(self, obj):
        """The register's own page for this entity.

        **This URL was wrong for as long as it existed, and wrong in the way
        that looks like it works.** It pointed at
        `home/uctovna-jednotka?id=<id>`, which is a route RUZ's front end does
        not serve: requesting it answers with the site's WAF rejection page
        ("The requested URL was rejected. Please consult your administrator.")
        and a support id, not a 404 and not the company. Every reader who
        clicked through from the Účtovné závierky section hit that page.

        The working route is `domain/accountingentity/show/<ruz_id>`, verified
        against the live register for the id in that report (`1587213`): it
        answers 200 and renders the correct entity. The id itself was never the
        problem -- the API accepts it -- so only the path changed.

        Kept as a link even though the documents are now downloadable here: it
        is the register's own record of the filing, and a reader checking our
        figures against the source should be able to reach it.
        """
        if obj.ruz_id:
            return f"https://www.registeruz.sk/cruz-public/domain/accountingentity/show/{obj.ruz_id}"
        return None

    def get_ruz_statements(self, obj):
        """How many účtovné závierky RUZ itself lists for this company.

        This is the denominator the "Účtovné závierky" section needs and the one
        number a reader cannot get from anywhere else on the page. The page
        shows the years *we* read; without this, a company whose statements RUZ
        holds and which the financials sync has not reached yet looks identical
        to a company that files nothing at all. Volkswagen Slovakia is exactly
        that case today: 37 statement IDs in RUZ, zero rows read here.

        The list is already loaded with the row -- `exclude` above keeps it off
        the *wire*, not out of memory -- so this is a `len` on it rather than a
        second query. Every one of the 445 626 rows holds a list (measured
        2026-09-12: 0 nulls, 0 non-arrays), so there is no other shape to
        handle.
        """
        return len(obj.id_uctovnych_zavierok or [])

    def get_ruz_annual_reports(self, obj):
        """The same count for výročné správy, which we do not read at all.

        Only 4 % of rows carry one and there is no endpoint here that fetches a
        report's body, so this is published as a count for one reason: so the
        section can say what exists and is not in this database, rather than
        leaving a reader to conclude it does not exist.
        """
        return len(obj.id_vyrocnych_sprav or [])

    def _get_orsr_profile(self, obj):
        try:
            return obj.orsr_profile
        except ObjectDoesNotExist:
            return None

    def _get_structured(self, profile):
        payload = getattr(profile, 'raw_payload', None) or {}
        structured = payload.get('structured') if isinstance(payload, dict) else None
        return structured or {}

    def get_executives(self, obj):
        profile = self._get_orsr_profile(obj)
        if not profile:
            return []

        structured = self._get_structured(profile)
        executives = []
        seen = set()

        def add(person, default_role):
            name = (person.get('name') or '').strip() if isinstance(person, dict) else str(person or '').strip()
            if not name:
                return
            key = re.sub(r'\W+', '', name.casefold())
            if not key or key in seen:
                return
            seen.add(key)
            role = ''
            if isinstance(person, dict):
                role = (person.get('role') or default_role).strip()
            else:
                role = default_role
            executives.append({'name': name, 'role': role or default_role})

        for person in structured.get('statutarny_organ', []):
            add(person, 'Konateľ')
        for person in structured.get('predstavenstvo', []):
            add(person, 'Člen predstavenstva')
        for person in structured.get('spravcovia', []):
            add(person, 'Správca')
        for person in structured.get('likvidatori', []):
            add(person, 'Likvidátor')
        for person in structured.get('starostovia', []):
            add(person, 'Starosta')
        for person in structured.get('primatori', []):
            add(person, 'Primátor')
        for person in structured.get('riaditelia', []):
            add(person, 'Riaditeľ')
        for person in structured.get('cirkevni_hodnostari', []):
            add(person, 'Cirkevný hodnostár')
        for person in structured.get('prokura', []):
            add(person, 'Prokurista')
        for person in structured.get('spolocnici', []):
            add(person, 'Spoločník')

        # Fallback na staré flat polia ak structured chýba
        if not executives:
            for name in self._extract_person_names(profile.statutarny_organ):
                add(name, 'Konateľ')
            for name in self._extract_person_names(getattr(profile, 'prokura', [])):
                add(name, 'Prokurista')
            for name in self._extract_person_names(profile.spolocnici):
                add(name, 'Spoločník')

        return executives

    def get_connections(self, obj):
        executives = self.get_executives(obj)
        status = 'Vymazaná' if obj.datum_zrusenia else 'Aktívna'
        return [
            {
                'companyName': person['name'],
                'ico': obj.ico,
                'role': person['role'],
                'status': status,
            }
            for person in executives
        ]

    def get_orsr_profile(self, obj):
        profile = self._get_orsr_profile(obj)
        if not profile:
            return None

        structured = self._get_structured(profile)
        oddiel_type = (profile.oddiel_type or self._detect_oddiel_type(profile.oddiel) or '').lower()

        result = {
            'oddiel': profile.oddiel,
            'oddiel_type': oddiel_type,
            'vlozka_cislo': profile.vlozka_cislo,
            'obchodne_meno': profile.obchodne_meno,
            'sidlo': profile.sidlo,
            'den_zapisu': profile.den_zapisu,
            'pravna_forma': profile.pravna_forma,
            'konanie': profile.konanie or structured.get('konanie') or profile.konanie_menom_spolocnosti,
            'konanie_menom_spolocnosti': profile.konanie_menom_spolocnosti,
            'vyska_zakladneho_imania': profile.vyska_zakladneho_imania,
            'predmet_podnikania': profile.predmet_podnikania,
            'raw_sections': profile.raw_sections,
            'orsr_aktualizacia_dat': profile.orsr_aktualizacia_dat,
            'orsr_datum_vypisu': profile.orsr_datum_vypisu,
            'fetch_ok': profile.fetch_ok,
            'last_error': profile.last_error,
            # Strukturované dáta (bohaté, s adresami, rolami, vznikom funkcie)
            'structured': structured,
            # Spätne kompatibilné flat polia
            'spolocnici': profile.spolocnici,
            'statutarny_organ': profile.statutarny_organ,
            'prokura': profile.prokura,
            'vklady_spolocnikov': profile.vklady_spolocnikov,
        }

        # Polia pre družstvá a osobitné typy
        if oddiel_type == 'dr' or profile.predstavenstvo or profile.kontrolna_komisia:
            result.update({
                'predstavenstvo': profile.predstavenstvo,
                'kontrolna_komisia': profile.kontrolna_komisia,
                'zakladny_clensky_vklad': profile.zakladny_clensky_vklad,
                'zapisovane_zakladne_imanie': profile.zapisovane_zakladne_imanie,
                'dalske_pravne_skutocnosti': profile.dalske_pravne_skutocnosti,
            })

        return result

    def _detect_oddiel_type(self, oddiel_text):
        if not oddiel_text:
            return ''
        return oddiel_text.strip().split()[0].lower()

    def _extract_person_names(self, raw_items):
        names = []
        seen = set()

        for raw in raw_items or []:
            text = (raw or '').strip()
            if not text:
                continue

            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if not lines:
                continue

            if len(lines) == 1:
                candidate = lines[0]
                normalized = candidate.lower()
                if any(normalized.startswith(prefix) for prefix in PERSON_SKIP_PREFIXES):
                    continue
                if re.search(r'\d', candidate):
                    continue
                if len(candidate.split()) < 2:
                    continue
                key = re.sub(r'\W+', '', candidate.casefold())
                if key and key not in seen:
                    seen.add(key)
                    names.append(candidate)
                continue

            parts = []
            for line in lines:
                normalized = line.lower()
                if any(normalized.startswith(prefix) for prefix in PERSON_SKIP_PREFIXES):
                    break
                if re.search(r'\d', line):
                    break
                parts.append(line)

            candidate = ' '.join(parts).strip()
            if len(candidate.split()) < 2:
                continue
            key = re.sub(r'\W+', '', candidate.casefold())
            if key and key not in seen:
                seen.add(key)
                names.append(candidate)

        return names


class SearchHistorySerializer(serializers.ModelSerializer):
    searchedAt = serializers.DateTimeField(source='searched_at', read_only=True)

    class Meta:
        model = SearchHistory
        fields = ['id', 'ico', 'name', 'searchedAt']
        read_only_fields = fields
