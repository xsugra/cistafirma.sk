from django.db import models
from django.db.models.functions import Upper
from django.utils.translation import gettext_lazy as _


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
    ico = models.CharField(
        max_length=8,
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
        verbose_name='Zisk',
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
    assets_inventory = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Zásoby')
    assets_receivables_long = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Dlhodobé pohľadávky')
    assets_receivables_short = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='Krátkodobé pohľadávky')
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
