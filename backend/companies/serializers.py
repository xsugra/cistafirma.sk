import re

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from core.constants import PERSON_SKIP_PREFIXES
from .models import Company, Watchlist, SectorBenchmark, SearchHistory
from .services.financial_analysis import FinancialAnalysisService
from .services.nace import get_nace_section, get_nace_section_name, get_nace_division_name


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
        c = obj.company
        total_debt = float(c.debt_vszp or 0) + float(c.debt_soc_poist or 0) + float(c.tax_debt or 0)
        if total_debt > 0:
            return max(5, int(70 - min(total_debt / 5000, 50)))
        return 100


class CompanyDetailSerializer(serializers.ModelSerializer):
    legal_form = serializers.CharField(source='get_legal_form_display', read_only=True)
    financials = serializers.SerializerMethodField()
    analysis = serializers.SerializerMethodField()
    benchmark = serializers.SerializerMethodField()
    executives = serializers.SerializerMethodField()
    connections = serializers.SerializerMethodField()
    orsr_profile = serializers.SerializerMethodField()
    ruz_portal_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = '__all__'

    def get_financials(self, obj):
        results = obj.financial_results.all().order_by('year')
        out = []
        for r in results:
            assets_total = float(r.assets_total or 0)
            liabilities_total = float(r.liabilities_total or 0)
            liabilities_accruals = float(r.liabilities_accruals or 0)
            revenue = float(r.revenue or 0)
            added_value = float(r.added_value or 0)

            debt_ratio = None
            if assets_total:
                debt_ratio = round((liabilities_total + liabilities_accruals) / assets_total * 100, 2)

            gross_margin = None
            if revenue:
                gross_margin = round(added_value / revenue * 100, 2)

            out.append({
                'year': r.year,
                'revenue': revenue,
                'profit': float(r.profit or 0),
                'totalRevenue': float(r.total_revenue or 0),
                'costs': float(r.costs or 0),
                'incomeTax': float(r.income_tax or 0),
                'incomeTaxPaid': float(r.income_tax_paid or 0),
                'assetsTotal': assets_total,
                'assetsIntangible': float(r.assets_intangible or 0),
                'assetsTangible': float(r.assets_tangible or 0),
                'assetsFinancial': float(r.assets_financial or 0),
                'assetsInventory': float(r.assets_inventory or 0),
                'assetsReceivablesLong': float(r.assets_receivables_long or 0),
                'assetsReceivablesShort': float(r.assets_receivables_short or 0),
                'assetsFinancialAccounts': float(r.assets_financial_accounts or 0),
                'assetsAccruals': float(r.assets_accruals or 0),
                'equity': float(r.equity or 0),
                'equityBasic': float(r.equity_basic or 0),
                'equityCapitalFunds': float(r.equity_capital_funds or 0),
                'equityProfitFunds': float(r.equity_profit_funds or 0),
                'equityRetained': float(r.equity_retained or 0),
                'liabilitiesTotal': liabilities_total,
                'liabilitiesReserves': float(r.liabilities_reserves or 0),
                'liabilitiesLong': float(r.liabilities_long or 0),
                'liabilitiesShort': float(r.liabilities_short or 0),
                'liabilitiesAccruals': liabilities_accruals,
                'addedValue': float(r.added_value or 0),
                'debtRatio': debt_ratio,
                'grossMargin': gross_margin,
            })
        return out

    def get_analysis(self, obj):
        results = list(obj.financial_results.all().order_by('year'))
        if not results:
            return None
        analysis = FinancialAnalysisService.analyze(results)
        return FinancialAnalysisService.to_dict(analysis)

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
        if obj.ruz_id:
            return f"https://www.registeruz.sk/cruz-public/home/uctovna-jednotka?id={obj.ruz_id}"
        return None

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
