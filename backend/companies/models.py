from django.db import models
from django.db.models.functions import Upper
from django.utils.translation import gettext_lazy as _

from companies import seat_matching
from companies.address import psc_key


# Číselník právnych foriem s gettext markermi pre i18n
LEGAL_FORMS = {
    '100': _('Physical person - casual activity - registered in tax system'),
    '101': _('Entrepreneur - physical person - not registered in commercial register'),
    '102': 'Podnikateľ-fyzická osoba-zapísaný v obchodnom registri',
    '103': 'Samostatne hospodáriaci roľník nezapísaný v obchodnom registri',
    '104': 'Samostatne hospodáriaci roľník zapísaný v obchodnom registri',
    '105': 'Slobodné povolanie-fyzická osoba podnikajúca na základe iného ako živnostenského zákona',
    '106': 'Slobodné povolanie-fyzická osoba podnikajúca na základe iného ako živnostenského zákona zapísaná v obchodnom registri',
    '107': 'Podnikateľ-fyzická osoba-nezapís.v OR-podnikajúca súčasne ako sam.hosp.roľník',
    '108': 'Podnikateľ-fyzická osoba-zapís.v OR-podnikajúca súčasne ako sam.hosp.roľník',
    '109': 'Podnikateľ-fyzická osoba-nezapís.v OR-podnikajúca súčasne ako osoba so slobodným povolaním',
    '110': 'Podnikateľ-fyzická osoba-zapís.v OR-podnikajúca súčasne ako osoba so slobodným povolaním',
    '111': 'Verejná obchodná spoločnosť',
    '112': 'Spoločnosť s ručením obmedzeným',
    '113': 'Komanditná spoločnosť',
    '117': 'Nadácia',
    '118': 'Neinvestičný fond',
    '119': 'Nezisková organizácia',
    '121': 'Akciová spoločnosť',
    '122': 'Európske zoskupenie hospodárskych záujmov',
    '123': 'Európska spoločnosť',
    '124': 'Európske družstvo',
    '125': 'Jednoduchá spoločnosť na akcie (nový kód RÚZ)',
    '205': 'Družstvo',
    '271': 'Spoločenstvá vlastníkov pozemkov, bytov a pod.',
    '272': 'Pozemkové spoločenstvo s právnou subjektivitou',
    '301': 'Štátny podnik',
    '311': 'Národná banka Slovenska',
    '312': 'Banka-štátny peňažný ústav',
    '321': 'Rozpočtová organizácia',
    '331': 'Príspevková organizácia',
    '381': 'Fondy',
    '382': 'Verejnoprávna inštitúcia',
    '383': 'Iná organizácia verejnej správy',
    '421': 'Zahraničná osoba, právnická osoba so sídlom mimo územia SR',
    '422': 'Zahraničná osoba, fyzická osoba s bydliskom mimo územia SR',
    '433': 'Sociálna a zdravotné poisťovne',
    '434': 'Doplnková dôchodková poisťovňa',
    '445': 'Komoditná burza',
    '701': 'Združenie (zväz, spolok, spoločnosť, klub ai.)',
    '711': 'Politická strana, politické hnutie',
    '721': 'Cirkevná organizácia',
    '741': 'Stavovská organizácia - profesná komora',
    '745': 'Komora (s výnimkou profesných komôr)',
    '751': 'Záujmové združenie právnických osôb',
    '752': 'Záujmové združenie fyzických osôb bez právnej spôsobilosti',
    '801': 'Obec (obecný úrad), mesto (mestský úrad)',
    '803': 'Samosprávny kraj (úrad samosprávneho kraja)',
    '804': 'Európske zoskupenie územnej spolupráce',
    '901': 'Zastupiteľské orgány iných štátov',
    '911': 'Zahraničné kultúrne, informačné stredisko, rozhlasová, tlačová a televízna agentúra',
    '921': 'Medzinárodné organizácie a združenia',
    '931': 'Zastúpenie zahraničnej právnickej osoby',
    '951': 'Miestna jednotka bez právnej spôsobilosti',
    '995': 'Nešpecifikovaná právna forma',
}

# Skratky právnych foriem pre admin zobrazenie
LEGAL_FORMS_SHORT = {
    '100': 'FO-príležitostná',
    '101': 'FO-podnikateľ',
    '102': 'FO-podnikateľ v OR',
    '103': 'SHR',
    '104': 'SHR v OR',
    '105': 'FO-slobodné povolanie',
    '106': 'FO-slobodné povolanie v OR',
    '107': 'FO-podnikateľ+SHR',
    '108': 'FO-podnikateľ+SHR v OR',
    '109': 'FO-podnikateľ+slobodné',
    '110': 'FO-podnikateľ+slobodné v OR',
    '111': 'v. o. s.',
    '112': 's. r. o.',
    '113': 'k. s.',
    '117': 'nadácia',
    '118': 'neinvestičný fond',
    '119': 'nezisková org.',
    '121': 'a. s.',
    '122': 'EZÚH',
    '123': 'európska spoločnosť',
    '124': 'európske družstvo',
    '205': 'družstvo',
    '271': 'spoločenstvo vlastníkov',
    '272': 'pozemkové spoločenstvo',
    '301': 'štátny podnik',
    '311': 'NBS',
    '312': 'banka-štátny ústav',
    '321': 'rozpočtová org.',
    '331': 'príspevková org.',
    '381': 'fondy',
    '382': 'verejnoprávna inštitúcia',
    '383': 'iná org. verejnej správy',
    '421': 'zahraničná PO',
    '422': 'zahraničná FO',
    '433': 'sociálne/zdravotné poisťovne',
    '434': 'doplnková dôchodková poisťovňa',
    '445': 'komoditná burza',
    '701': 'združenie',
    '711': 'politická strana',
    '721': 'cirkevná org.',
    '741': 'profesná komora',
    '745': 'komora',
    '751': 'záujmové združenie PO',
    '752': 'záujmové združenie FO',
    '801': 'obec/mesto',
    '803': 'samosprávny kraj',
    '804': 'EZÚS',
    '901': 'zastupiteľské orgány štátov',
    '911': 'zahraničné kultúrne stredisko',
    '921': 'medzinárodné org.',
    '931': 'zastúpenie zahraničnej PO',
    '951': 'miestna jednotka',
    '995': 'nešpecifikovaná',
}

# Choices (helper for admin / UI). Keep as a separate constant — we do NOT bind
# this to the model field (Option A). Sorted by code for stable presentation.
LEGAL_FORMS_CHOICES = sorted(
    [(code, f"{code} - {name}") for code, name in LEGAL_FORMS.items()], key=lambda t: t[0]
)


import logging
_logger = logging.getLogger(__name__)

# Keep track of unknown codes we've already logged to avoid log spam
_logged_unknown_legal_form_codes: set[str] = set()

# Metrics counters (will be initialized if Prometheus is available)
try:
	from prometheus_client import Counter
	UNKNOWN_LEGAL_FORM_CODE_COUNT = Counter(
		'unknown_legal_form_codes_total',
		'Total count of unknown legal form codes encountered',
		['code', 'source']
	)
	PROMETHEUS_AVAILABLE = True
except ImportError:
	PROMETHEUS_AVAILABLE = False

# Sentry client (will be initialized if sentry-sdk is available)
try:
	import sentry_sdk
	SENTRY_AVAILABLE = True
except ImportError:
	SENTRY_AVAILABLE = False


def normalize_legal_form_code(value) -> str:
	"""
	Normalize incoming legal form value into a canonical string code.

	Rules:
	- None / empty -> return '995' (Nešpecifikovaná)
	- Strip whitespace, convert to string
	- If resulting code is not present in LEGAL_FORMS keys, log it once and
	  return '995'

	Metrics:
	- Increments prometheus counter for unknown codes (if available)
	- Sends to Sentry for unknown codes (if available)
	"""
	if value is None:
		return '995'
	try:
		code = str(value).strip()
	except Exception:
		return '995'
	if not code:
		return '995'

	# Build candidate variants to try matching (handle leading zeros and numeric values)
	candidates = [code]
	if code.isdigit():
		candidates.insert(0, str(int(code)))
		# also try stripping leading zeros (if any)
		stripped = code.lstrip('0')
		if stripped:
			candidates.append(stripped)

	for cand in candidates:
		if cand in LEGAL_FORMS:
			return cand

	# Not recognized — log once and fall back to '995'
	if code not in _logged_unknown_legal_form_codes:
		_logger.info("Unknown legal form code encountered during normalization: %s", code)
		_logged_unknown_legal_form_codes.add(code)

		# Report to Prometheus if available
		if PROMETHEUS_AVAILABLE:
			try:
				UNKNOWN_LEGAL_FORM_CODE_COUNT.labels(code=code, source='normalize_legal_form_code').inc()
			except Exception as e:
				_logger.warning("Failed to increment Prometheus counter for unknown code %s: %s", code, e)

		# Report to Sentry if available
		if SENTRY_AVAILABLE:
			try:
				sentry_sdk.capture_message(
					f"Unknown legal form code: {code}",
					level='warning',
					tags={
						'event_type': 'unknown_legal_form',
						'code': code,
					}
				)
			except Exception as e:
				_logger.warning("Failed to send Sentry report for unknown code %s: %s", code, e)

	return '995'


# Definícia SZCO (self-employed/samostatne zárobkovo činné osoby)
# Kódy: 100-110 sú individuálne osoby (fyzické osoby podnikajúce rôznymi formami)
SZCO_LEGAL_FORMS = {'100', '101', '102', '103', '104', '105', '106', '107', '108', '109', '110'}


def is_szco_company(legal_form_code: str) -> bool:
	"""
	Zisťuje, či je subjekt SZCO (samozaměstnaný/fyzická osoba s podnikateľskou činnosťou).
	SZCO sú právne formy s kódmi 100-110.

	Args:
		legal_form_code: Normalizovaný kód právnej formy (napr. '101', '112')

	Returns:
		True ak je SZCO, False ak je Firma (PO - právnická osoba)
	"""
	return str(legal_form_code).strip() in SZCO_LEGAL_FORMS


def is_company_company(legal_form_code: str) -> bool:
	"""
	Zisťuje, či je subjekt Firma (právnická osoba).
	Opak is_szco_company.

	Args:
		legal_form_code: Normalizovaný kód právnej formy (napr. '112', '121')

	Returns:
		True ak je Firma, False ak je SZCO
	"""
	return not is_szco_company(legal_form_code)


class Company(
    models.Model,
):
    """
    Represents a company (účtovná jednotka) from the RUZ API.
    """
    ruz_id = models.IntegerField(
        unique=True,
        help_text="Identifikátor účtovnej jednotky z RUZ API",
        db_column="RUZ ID",
    )
    # 20, not 8. RUZ gives organisational units a **12-character** IČO --
    # `001781521576` is the parent's `00178152` plus a four-digit serial -- and
    # at 8 the row could not be stored at all: Postgres refused it with `value
    # too long for type character varying(8)`, the walk counted the record as a
    # failure, and the company never arrived. Measured 2026-09-13 on RUZ id
    # 1520199 (`SZZ Základná organizácia 43-1`, Ružomberok), which publishes 13
    # statements we could not see.
    #
    # `unique` stays. Measured: 449 763 rows, **zero** IČO shared by two of
    # them; a duplicate is an edge population, not a property of the register,
    # and 13 read sites do `.get(ico=...)` where a second row would mean HTTP
    # 500. What the walk writes is keyed on `ruz_id` (the register's own key,
    # already unique) so a duplicate IČO can never silently swap two entities'
    # identities. See docs/PLAN.md #90 for the deferred API decision.
    ico = models.CharField(
        max_length=20,
        unique=True,
        help_text="IČO účtovnej jednotky",
        db_column="ICO",
    )
    dic = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="DIČ účtovnej jednotky",
        db_column="DIC",
    )
    sid = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        help_text="SID účtovnej jednotky",
        db_column="SID",
    )
    nazov_UJ = models.CharField(
        max_length=500,
        help_text="Názov účtovnej jednotky",
        db_column="Názov UJ",
    )
    mesto = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Adresa účtovnej jednotky, mesto",
        db_column="Mesto",
    )
    ulica = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Adresa účtovnej jednotky, ulica s číslom",
        db_column="Ulica",
    )
    psc = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Adresa účtovnej jednotky, PSČ",
        db_column="PSČ",
    )

    # Sídlo umiestnené na skutočný adresný bod, nad rámec `PostalCodeArea`.
    #
    # `postal_code` je to, čo mapa kreslila doteraz — kruh okolo stredu PSČ,
    # ktorého stred je od vlastných adresných bodov medián 1 980 m. `building`
    # je budova z registra adries (`AddressPoint`); `street` je stred ulice,
    # keď budova známa nie je. Prázdne pole znamená, že firmu umiestniť nevieme
    # — a to je čestný stav, nie chyba: **14,5 %** riadkov (65 324 zo 449 764)
    # má adresu, ktorú register adries neumiestni, a tie si nechajú PSČ kruh.
    #
    # To číslo je z celého behu, nie zo vzorky. Skoršie znenie tu malo 20,9 %,
    # čo je doplnok k 79,1 % — k číslu z 4 000-firmového výseku `order_by(
    # "ruz_id")[:4000]`, ktorý je geografická hlava krajiny a ktorý #98 zahodil.
    # Rozdiel 6,4 bodu je presne tá chyba, ktorú tu celý čas pomenúvame: číslo,
    # ktorého populácia nie je tá, ktorú veta tvrdí.
    #
    # `seat_precision` je **tvrdenie o presnosti**, preto je to vlastný stĺpec
    # a nie odvodenina z toho, či súradnica existuje: budova sa kreslí ako bod
    # a ulica ako kruh, a zámena tých dvoch je presne tá nadsázka, ktorú #98
    # pomenoval.
    #
    # Stĺpce sú odvodené a prepočítateľné (`match_seat_addresses`); zdrojom
    # pravdy zostáva `ulica`/`mesto`/`psc` vyššie. Nepíše ich synchronizácia
    # z RUZ, takže import firmy ich neprepíše.
    seat_lat = models.FloatField(blank=True, null=True, verbose_name='Sídlo — zemepisná šírka')
    seat_lon = models.FloatField(blank=True, null=True, verbose_name='Sídlo — zemepisná dĺžka')
    seat_precision = models.CharField(
        max_length=20,
        blank=True,
        choices=seat_matching.SEAT_PRECISION_CHOICES,
        verbose_name='Presnosť sídla',
        help_text='building = budova, street = stred ulice, postal_code = len PSČ',
    )
    seat_radius_m = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Polomer sídla (m)',
        help_text='0 pri budove; pri ulici polomer, ktorý pokryje 90 % jej bodov',
    )
    seat_point_count = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name='Počet adresných bodov',
        help_text='Z koľkých bodov registra je sídlo počítané',
    )
    seat_tier = models.CharField(
        max_length=40,
        blank=True,
        verbose_name='Vrstva párovania',
        help_text='Ktorá vrstva odpovedala (psc_ulica_orient, …) — dôkaz, nie popis',
    )
    seat_matched_at = models.DateTimeField(
        blank=True, null=True, verbose_name='Sídlo spárované'
    )
    datum_zalozenia = models.DateField(
        blank=True,
        null=True,
        help_text="Dátum založenia účtovnej jednotky",
        db_column="Dátum založenia UJ",
    )
    datum_zrusenia = models.DateField(
        blank=True,
        null=True,
        help_text="Dátum zrušenia účtovnej jednotky",
        db_column="Dátum zrušenia UJ",
    )
    pravna_forma = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kód právnej formy",
        db_column="Právna forma",
    )
    sk_NACE = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kód SK NACE klasifikácie",
        db_column="NACE",
    )
    velkost_organizacie = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kód kategórie veľkosti organizácie",
        db_column="Veľkosť",
    )
    druh_vlastnictva = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kód druhu vlastníctva",
        db_column="Vlastníctvo",
    )
    kraj = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Sídlo účtovnej jednotky, kód kraja",
        db_column="Kraj",
    )
    okres = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Sídlo účtovnej jednotky, kód okresu",
        db_column="Okres",
    )
    sidlo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Sídlo účtovnej jednotky, kód obce alebo mesta",
        db_column="Sídlo",
    )
    konsolidovana = models.BooleanField(
        default=False,
        help_text="Príznak, či jednotka obsahuje aspoň jednu konsolidovanú účtovnú závierku",
        db_column="Konsolidovaná",
    )
    uses_ifrs = models.BooleanField(
        default=False,
        help_text="Firma účtuje podľa IFRS — finančné výkazy sú v RUZ len ako PDF",
        db_column="Používa IFRS",
    )
    id_uctovnych_zavierok = models.JSONField(
        default=list,
        help_text="Zoznam identifikátorov všetkých súvisiacich účtovných závierok",
        db_column="ID UZ",
    )
    id_vyrocnych_sprav = models.JSONField(
        default=list,
        help_text="Zoznam identifikátorov všetkých súvisiacich výročných správ",
        db_column="ID VS",
    )
    zdroj_dat = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Kód zdroja, z ktorého pochádzajú dáta",
        db_column="Kód zdroja",
    )
    datum_poslednej_upravy = models.DateField(
        null=True,
        blank=True,
        help_text="Dátum poslednej úpravy",
        db_column="Dátum a čas kontroly RUZ",
    )

    """
    Represents a debt of company in VSZP and Socialna Poistovna (Life and Social Insurance).
    """
    debt_vszp = models.DecimalField(
        verbose_name="Dlh vo VSZP",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dlh vo Všeobecnej zdravotnej poisťovni",
        db_column="Dlh vo VSZP"
    )
    debt_soc_poist = models.DecimalField(
        verbose_name="Dlh v SP",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dlh v Sociálnej poisťovni",
        db_column="Dlh v SP"
    )
    # The SP registry publishes two kinds of entry under one heading, and only
    # one of them is a sum: a company owing at least 5,00 € carries an amount,
    # while an employer that failed to submit its výkaz poistného a príspevkov
    # -- or a foreign SZČO that failed to report income and expenses -- is
    # listed with a bare hyphen in the amount column and the missing periods
    # beside it (measured on the live site 2026-09-15). Around one row in ten
    # of the register's 131 510 debtors is of the second kind.
    #
    # `debt_soc_poist` cannot hold that fact: NULL there means "no debt", which
    # is exactly the wrong thing to show, and the company page said it for
    # every one of these because `total_debt` reads NULL as zero. So the
    # listing gets its own column -- and no figure is ever written for it,
    # because the register never published one.
    #
    # NULL is "not known": every company checked before this column existed,
    # and every company the rotation has not reached. It is deliberately not
    # collapsed into False, so "we have not looked" never reads as "we looked
    # and there is nothing" -- the same distinction the company page draws from
    # the two check dates.
    social_listed_without_amount = models.BooleanField(
        verbose_name="Evidencia v SP bez sumy",
        null=True,
        blank=True,
        help_text=(
            "Sociálna poisťovňa uvádza spoločnosť v zozname dlžníkov bez "
            "zverejnenej sumy (nesplnená vykazovacia povinnosť)"
        ),
        db_column="SP bez zverejnenej sumy",
    )
    last_insurance_debt = models.DateTimeField(
        verbose_name="Posledná kontrola dlhov vo VSZP a SP",
        null=True,
        blank=True,
        help_text="Dátum a čas poslednej kontroly dlhov v poisťovniach",
        db_column="Dátum a čas kontroly VSZP/SP"
    )

    """
    Represents analyses from Financna sprava (FS)
    """

    tax_debt = models.DecimalField(
        verbose_name="Daňový dlh",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dlh na daniach z FS",
        db_column="Daňový dlh",
    )
    vat_payer = models.BooleanField(
        verbose_name="Platiteľ DPH",
        null=True,
        blank=True,
        help_text="Je platiteľ DPH? z FS",
        db_column="Platiteľ DPH",
    )
    ic_dph = models.CharField(
        verbose_name="IČ DPH",
        max_length=20,
        null=True,
        blank=True,
        help_text="Identifikačné číslo pre daň z pridanej hodnoty",
        db_column="IČ DPH",
    )
    datum_reg_dph = models.DateField(
        verbose_name="Dátum registrácie DPH",
        null=True,
        blank=True,
        help_text="Dátum registrácie subjektu pre DPH",
        db_column="Dátum registrácie DPH",
    )
    bank_accounts = models.JSONField(
        verbose_name="Bankové účty",
        default=list,
        blank=True,
        help_text="Zoznam bankových účtov subjektu pre DPH",
        db_column="IBANs",
    )
    vat_deleted_date = models.DateField(
        verbose_name="Dátum výmazu z DPH",
        null=True,
        blank=True,
        help_text="Dátum výmazu zo zoznamu platiteľov DPH",
        db_column="Dátum výmazu DPH",
    )
    vat_deleted_reason = models.CharField(
        verbose_name="Dôvod výmazu z DPH",
        max_length=100,
        null=True,
        blank=True,
        help_text="Dôvod výmazu zo zoznamu platiteľov DPH",
        db_column="Dôvod výmazu DPH",
    )
    tax_reliability = models.CharField(
        verbose_name="Index daňovej spoľahlivosti",
        max_length=50,
        null=True,
        blank=True,
        help_text="Index daňovej spoľahlivosti z FS (spoľahlivý, vysoko spoľahlivý, nespoľahlivý)",
        db_column="Index daňovej spoľahlivosti",
    )
    fs_update_date = models.DateTimeField(
        verbose_name="Posledná aktualizácia z FS",
        null=True,
        blank=True,
        help_text="Dátum poslednej aktualizácie dát z FS",
        db_column="Dátum kontroly FS",
    )

    class Meta:
        db_table = "Companies and SZCO"
        verbose_name = "Firma"
        verbose_name_plural = "Firmy"
        ordering = ['-datum_poslednej_upravy', 'nazov_UJ']
        indexes = [
            models.Index(fields=['mesto'], name='company_mesto_idx'),
            models.Index(fields=['psc'], name='company_psc_idx'),
            models.Index(fields=['kraj'], name='company_kraj_idx'),
            models.Index(fields=['sk_NACE'], name='company_nace_idx'),
            models.Index(fields=['sk_NACE', 'datum_zrusenia'], name='company_nace_active_idx'),
            models.Index(Upper('mesto'), name='company_mesto_ci_idx'),
            models.Index(Upper('sk_NACE'), name='company_nace_ci_idx'),
            models.Index(fields=['pravna_forma'], name='company_pravna_forma_idx'),
            models.Index(fields=['velkost_organizacie'], name='company_velkost_org_idx'),
            models.Index(fields=['datum_zalozenia'], name='company_datum_zaloz_idx'),
            models.Index(fields=['debt_vszp'], name='company_debt_vszp_idx'),
            models.Index(fields=['debt_soc_poist'], name='company_debt_sp_idx'),
            models.Index(fields=['tax_debt'], name='company_tax_debt_idx'),
            models.Index(fields=['kraj', 'datum_zrusenia'], name='company_kraj_active_idx'),
            models.Index(fields=['pravna_forma', 'datum_zrusenia'], name='company_form_active_idx'),
            models.Index(fields=['mesto', 'datum_zrusenia'], name='company_mesto_active_idx'),
            models.Index(fields=['velkost_organizacie', 'datum_zrusenia'], name='company_size_active_idx'),
        ]

    def __str__(self):
        return self.nazov_UJ
    
    def get_legal_form_display(self):
        """Vráti ľudsky čitateľný názov právnej formy"""
        if not self.pravna_forma:
            return ''
        return LEGAL_FORMS.get(str(self.pravna_forma), f'Neznáma forma ({self.pravna_forma})')
    
    def get_legal_form_short(self):
        """Vráti skratku právnej formy"""
        if not self.pravna_forma:
            return ''
        return LEGAL_FORMS_SHORT.get(str(self.pravna_forma), f'Neznáma ({self.pravna_forma})')
    
    def get_legal_form_with_code(self):
        """Vráti kód so skratkou právnej formy pre admin zobrazenie"""
        if not self.pravna_forma:
            return ''
        legal_short = LEGAL_FORMS_SHORT.get(str(self.pravna_forma), 'Neznáma forma')
        return f"{self.pravna_forma} - {legal_short}"


class Watchlist(models.Model):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='watchlist',
        db_column='user_id',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='watchers',
        db_column='company_id',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'Watchlist'
        unique_together = [('user', 'company')]
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user} → {self.company.ico}"


class SearchHistory(models.Model):
    """História vyhľadávaní používateľa."""

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='search_history',
    )
    ico = models.CharField(max_length=20, verbose_name='IČO')
    name = models.CharField(max_length=255, verbose_name='Názov firmy')
    searched_at = models.DateTimeField(auto_now_add=True, verbose_name='Vyhľadané')

    class Meta:
        db_table = 'Search History'
        verbose_name = 'História vyhľadávania'
        verbose_name_plural = 'História vyhľadávania'
        ordering = ['-searched_at']
        indexes = [
            models.Index(fields=['user', '-searched_at']),
        ]

    def __str__(self):
        return f"{self.user} → {self.ico} @ {self.searched_at}"


class CompanyFinancialResult(models.Model):
    """Hospodárske výsledky firmy po rokoch pre grafy vo frontende."""

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='financial_results',
        verbose_name='Firma',
    )
    year = models.PositiveIntegerField(verbose_name='Rok')
    revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Tržby',
    )
    profit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Výsledok hospodárenia z hospodárskej činnosti',
    )
    # Two different accounting rows used to share `profit`, chosen between by
    # `_pick_better` -- i.e. by whichever had the larger absolute value. Measured
    # 2026-09-12 on the 4 383 rows where a non-zero tax makes the two
    # distinguishable: 3 788 held the pre-tax operating result, 23 the after-tax
    # result, and all 23 were loss-making (a loss grows once tax is deducted, so
    # the absolute-value rule picked the post-tax row exactly there). The field
    # was displayed as "Zisk po zdanení" throughout, so a pre-tax figure was
    # being read as an after-tax one -- for 86 % of the rows where the question
    # can be settled at all.
    #
    # `profit` is now the operating result and nothing else, and the after-tax
    # row has its own field. Nullable, and deliberately not back-filled: a row
    # that has not been re-read since this split genuinely does not carry the
    # figure, and showing a `profit` value under this label would be the same
    # substitution in a new place.
    profit_after_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Zisk po zdanení',
    )

    # Výkaz ziskov a strát — rozšírenie
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Celkové výnosy')
    costs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Celkové náklady')
    added_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Pridaná hodnota')
    income_tax = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Daň z príjmu')
    income_tax_paid = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Splatná daň')

    # Súvaha — aktíva
    assets_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Aktíva celkom')
    assets_intangible = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Dlhodobý nehmotný majetok')
    assets_tangible = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Dlhodobý hmotný majetok')
    assets_financial = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Dlhodobý finančný majetok')
    assets_current = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Obežný majetok celkom')
    assets_inventory = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Zásoby')
    assets_receivables_long = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Dlhodobé pohľadávky')
    assets_receivables_short = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Krátkodobé pohľadávky')
    assets_financial_short = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Krátkodobý finančný majetok')
    assets_financial_accounts = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Finančné účty')
    assets_accruals = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Časové rozlíšenie (aktíva)')

    # Súvaha — pasíva
    equity = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Vlastný kapitál')
    equity_basic = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Základné imanie')
    equity_capital_funds = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Kapitálové fondy')
    equity_profit_funds = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Fondy zo zisku')
    equity_retained = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='VH minulých rokov')
    liabilities_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Cudzie zdroje celkom')
    liabilities_reserves = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Rezervy')
    liabilities_long = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Dlhodobé záväzky')
    liabilities_short = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Krátkodobé záväzky')
    liabilities_accruals = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Časové rozlíšenie (pasíva)')

    source = models.CharField(
        max_length=30,
        blank=True,
        default='manual',
        verbose_name='Zdroj',
    )

    # Which revision of the RUZ parser read this row, stamped on every write
    # from `ruz_financials_sync.PARSER_REVISION`.
    #
    # The row is otherwise the only record of how it was read: it stores no
    # template id and no parser version, so before this field the only way to
    # tell two vintages apart was `updated_at` plus a live re-read. That is how
    # the accrual asymmetry was found (24 323 rows carrying only one side of
    # `časové rozlíšenie` collapsed to 864 under a re-read) -- and it is also how
    # a wrong explanation survived long enough to be written into
    # docs/SOURCE_DATA_INTEGRITY.md and then refuted by the same measurement, a
    # 97.7% gap in `assets_financial_short` that a fuller parser filled on 1.8%
    # of fresh rows.
    #
    # NULL means "written before this field existed", which is not the same as
    # "written by the oldest parser" and is not read as either. `profit_after_tax`
    # above is the precedent for the rest of it: a row that has not been re-read
    # genuinely does not carry the newer reading, and this field is what finally
    # says *which* rows those are instead of leaving it to be guessed.
    parser_revision = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
        db_index=True,
        verbose_name='Revízia parsera',
    )

    # The RUZ `účtovná závierka` this row was read from -- the filing for one
    # year, and the anchor the documents are reached through.
    #
    # Deliberately the *statement* and not the `účtovný výkaz` inside it: one
    # závierka holds a list of výkazy (súvaha, výkaz ziskov a strát, poznámky),
    # and which of them carried a given figure is a property of the parser run,
    # not of the year. Anchoring on the statement is what makes "every document
    # for this year" well defined; the výkazy are enumerated from it when
    # someone actually asks (`companies/services/ruz_documents.py`).
    #
    # Why store rather than resolve on demand: `_read_company` already holds this
    # id when it writes the row -- it is that loop's own variable -- so recording
    # it costs no request at all. Resolving year -> statement at page-view time
    # instead would mean walking the company's whole statement list and calling
    # `uctovna-zavierka` for each until one matched the year.
    #
    # Nullable because the 54 519 rows already stored were written before this
    # existed. `ruz_documents` resolves those live and caches the answer here, so
    # an un-backfilled row costs a request once rather than once per view. NULL
    # means "we have not recorded this", never "RUZ has no document for this
    # year" -- the distinction this whole section is built on.
    ruz_statement_id = models.BigIntegerField(
        null=True,
        blank=True,
        editable=False,
        db_index=True,
        verbose_name='ID účtovnej závierky v RUZ',
    )

    updated_at = models.DateTimeField(auto_now=True, verbose_name='Aktualizované')

    class Meta:
        db_table = 'Company Financial Results'
        verbose_name = 'Hospodársky výsledok'
        verbose_name_plural = 'Hospodárske výsledky'
        ordering = ['-year']
        unique_together = [('company', 'year')]
        indexes = [
            models.Index(fields=['company'], name='cfr_company_idx'),
            models.Index(fields=['company', '-year'], name='cfr_company_year_idx'),
            models.Index(fields=['year'], name='cfr_year_idx'),
            models.Index(fields=['company', 'year'], name='cfr_company_year_unique_idx'),
        ]

    def __str__(self):
        return f"{self.company.ico} - {self.year}"


class SectorBenchmark(models.Model):
    """Predpočítané sektorové benchmarky (mediány) pre finančné ukazovatele.

    Počítané periodicky cez Celery Beat (raz denne).
    """

    nace_section = models.CharField(
        max_length=5,
        verbose_name='NACE sekcia',
        help_text='Písmeno sekcie A-U',
    )
    year = models.PositiveIntegerField(verbose_name='Rok')
    company_count = models.PositiveIntegerField(
        verbose_name='Počet firiem',
        help_text='Koľko firiem bolo použitých na výpočet',
    )

    # Mediány kľúčových metrík (všetky nullable — niektoré sekcie nemusia mať dáta)
    median_revenue = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    median_profit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    median_assets_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    median_equity = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    median_roa = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_roe = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_ros = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_debt_ratio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_gross_margin = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_current_ratio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_self_financing_ratio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    computed_at = models.DateTimeField(auto_now=True, verbose_name='Vypočítané')

    class Meta:
        db_table = 'Sector Benchmarks'
        verbose_name = 'Sektorový benchmark'
        verbose_name_plural = 'Sektorové benchmarky'
        unique_together = [('nace_section', 'year')]
        ordering = ['nace_section', '-year']

    def __str__(self):
        return f"NACE {self.nace_section} — {self.year} ({self.company_count} firiem)"


# Najmenšia vzorka adresných bodov, z ktorej vôbec umiestnime špendlík.
#
# Register má päť PSČ s menej než 20 bodmi a tie pokrývajú 26 z našich
# 449 763 riadkov (0,01 %). Jednobodová „oblasť" dáva polomer 0 m, teda
# špendlík tvrdiaci presnosť vchodu do budovy — presne tá nadsázka, ktorú
# chceme vylúčiť. Pod touto hranicou sa neukladá nič a UI mapu neukáže;
# rovnaká disciplína ako pri 224 riadkoch registra, ktoré nemajú PSČ.
MIN_ADDRESS_POINTS = 20


class PostalCodeArea(models.Model):
    """PSČ ako miesto na mape, odvodené z registra adries MV SR.

    Toto je spojenie medzi sídlom firmy a súradnicou — a je to **PSČ, nie
    `mesto`**, zámerne. Pri 2 817 obciach zdroja leží 95 názvov vo viac než
    jednom okrese a náš zápis je iný než registrový (`Bratislava - mestská
    časť Ružinov` vs `Bratislava-Ružinov`), takže spojenie na názov by bolo
    fuzzy párovanie. PSČ pokrýva 441 165 zo 449 763 riadkov (98,09 %) a názvy
    nepotrebuje vôbec.

    Presnosť je **polomer, nie bod**: `radius_m` je polomer, ktorý pokryje
    90 % adresných bodov danej PSČ. Medián je 1 980 m, p90 4 118 m — preto to
    UI kreslí ako kruh a nie ako holý špendlík.
    """

    psc = models.CharField(
        max_length=5,
        unique=True,
        verbose_name='PSČ',
        help_text='Normalizovaná podoba bez medzier — kľúč spojenia s Company.psc',
    )
    lat = models.FloatField(verbose_name='Zemepisná šírka')
    lon = models.FloatField(verbose_name='Zemepisná dĺžka')
    radius_m = models.PositiveIntegerField(
        verbose_name='Polomer (m)',
        help_text='Pokryje 90 % adresných bodov tejto PSČ. Medián 1 980 m',
    )
    point_count = models.PositiveIntegerField(
        verbose_name='Počet adresných bodov',
        help_text=f'Z koľkých bodov je počítaný; pod {MIN_ADDRESS_POINTS} sa oblasť neukladá',
    )

    # Opisné, NIE kľúč. `dominant_obec` je najčastejšia obec v danej PSČ a pri
    # 836 PSČ, ktoré ležia vo viac než jednej obci, to nie je identita.
    # `obec_count` je práve to počítadlo — je to dôkaz o povahe kľúča, nie popis.
    dominant_obec = models.CharField(max_length=200, blank=True, verbose_name='Prevažujúca obec')
    obec_count = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Počet obcí v PSČ',
        help_text='Koľko obcí táto PSČ pokrýva; 1 = sedí s obcou',
    )
    okres = models.CharField(max_length=200, blank=True, verbose_name='Okres')
    kraj = models.CharField(max_length=100, blank=True, verbose_name='Kraj')

    source_version = models.CharField(
        max_length=40,
        blank=True,
        verbose_name='Verzia zdroja',
        help_text='dct:modified datasetu, z ktorého dáta sú (formát YYYY-MM-DD)',
    )
    imported_at = models.DateTimeField(auto_now=True, verbose_name='Importované')

    class Meta:
        verbose_name = 'PSČ oblasť'
        verbose_name_plural = 'PSČ oblasti'
        ordering = ['psc']
        indexes = [models.Index(fields=['okres'], name='pscarea_okres_idx')]

    def __str__(self):
        where = self.dominant_obec or self.okres or '?'
        return f'{self.psc} {where} (±{self.radius_m} m)'

    @staticmethod
    def normalize_psc(value):
        """PSČ bez medzier — jediná normalizácia v tomto toku.

        `Company.psc` má tri hodnoty s medzerou (`602 00`, `024 01`, `941 01`)
        a register ich píše bez, takže bez tohto by tie tri firmy ticho
        nesadli. Presne tá chyba, ktorú má #90 pomenovanú pri IČO: dve rôzne
        normalizácie na dvoch koncoch toho istého toku.

        Telo je `companies.address.psc_key`, pretože ten istý kľúč stavia aj
        `match_seat_addresses` a `import_address_points`. Kým bol tento kód
        napísaný dvakrát, tie dve strany sa rozišli presne na tých troch
        hodnotách: import medzeru odstránil, matcher ju `normalize_text`-om
        nechal, a každá PSČ vrstva pre tie firmy ticho minula. Definícia je
        preto v `address.py` — `models.py` importuje `seat_matching`, takže
        opačný smer by bol cyklus.
        """
        return psc_key(value)


class AddressPoint(models.Model):
    """Jeden adresný bod registra adries MV SR — budova, nie oblasť.

    `PostalCodeArea` je hrubá vrstva: PSČ, ktorého stred je od vlastných
    adresných bodov medián 1 980 m. Toto je jemná vrstva — **ten istý súbor**,
    ktorý už sťahujeme, len s ulicou, oboma číslami a súradnicou, takže firma
    sa dá umiestniť na svoju budovu namiesto na stred PSČ. Žiadny nový zdroj,
    žiadna registrácia, žiadna karta.

    `ulica` je **kľúč, nie popis**: je to výstup `companies.address.street_key`
    a tou istou funkciou prechádzajú obe strany spojenia — tento import aj naše
    vlastné riadky. Rovnaká disciplína ako pri `PostalCodeArea.psc`. Zdroj píše
    `Bratislavská ulica`, `17.novembra` a `m. schneidra trnavskeho`, naše riadky
    `Bratislavská`, `17. novembra` a `M. Schneidra-Trnavského`; bez spoločnej
    normalizácie by tie riadky ticho nesadli.

    Riadok s **prázdnym `ulica` je vidiecky** — register tak označuje 973 318
    zo svojich 1 739 536 riadkov a číslo potom nesie adresu samo. Do tejto
    tabuľky sa ich dostane **943 949**, zvyšok nemá súradnicu; to je celý rozdiel
    medzi 1 739 536 riadkami súboru a 1 704 346 riadkami tabuľky. Preto
    neexistuje druhá sada stĺpcov pre vidiek: je to ten istý kľúč s prázdnym
    názvom ulice.

    Tabuľka je **referenčná a nahradzovaná celá** pri každom importe (štvrťročne,
    ako zdroj), preto nemá `imported_at` po riadkoch — to by 1,7-miliónkrát
    zopakovalo jeden údaj. Kedy je snímka z dátumu zdroja nesie `source_version`
    a hlásenie príkazu.
    """

    psc = models.CharField(max_length=5, verbose_name='PSČ')
    obec = models.CharField(
        max_length=200,
        verbose_name='Obec',
        help_text='Normalizovaná podoba — kľúč spojenia s Company.mesto',
    )
    ulica = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Ulica',
        help_text='Normalizovaný kľúč; prázdne = vidiecky riadok, adresu nesie číslo',
    )
    supisne_cislo = models.CharField(max_length=20, blank=True, verbose_name='Súpisné číslo')
    orientacne_cislo = models.CharField(max_length=20, blank=True, verbose_name='Orientačné číslo')

    lat = models.FloatField(verbose_name='Zemepisná šírka')
    lon = models.FloatField(verbose_name='Zemepisná dĺžka')

    source_version = models.CharField(
        max_length=40,
        blank=True,
        verbose_name='Verzia zdroja',
        help_text='dct:modified datasetu, z ktorého dáta sú (formát YYYY-MM-DD)',
    )

    class Meta:
        verbose_name = 'Adresný bod'
        verbose_name_plural = 'Adresné body'
        indexes = [
            # Štyri sady stĺpcov a nič viac. Uličná vrstva je obslúžená
            # vedúcimi stĺpcami budovového indexu a vidiek je tá istá trojica
            # s prázdnou ulicou, takže na obe netreba index zvlášť.
            models.Index(fields=['psc', 'ulica', 'orientacne_cislo'], name='addr_psc_ul_orient_idx'),
            models.Index(fields=['psc', 'ulica', 'supisne_cislo'], name='addr_psc_ul_supis_idx'),
            models.Index(fields=['obec', 'ulica', 'orientacne_cislo'], name='addr_obec_ul_orient_idx'),
            models.Index(fields=['obec', 'ulica', 'supisne_cislo'], name='addr_obec_ul_supis_idx'),
        ]

    def __str__(self):
        street = self.ulica or self.obec
        number = self.orientacne_cislo or self.supisne_cislo
        return f'{street} {number}, {self.psc}'.strip()
