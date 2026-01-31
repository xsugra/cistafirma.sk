from django.db import models
from django.utils import timezone


class Company(
    models.Model,
):
    """
    Represents a company (účtovná jednotka) from the RUZ API.
    """
    ruz_id = models.IntegerField(
        unique = True,
        help_text = "Identifikátor účtovnej jednotky z RUZ API",
        db_column="RUZ ID",
    )
    ico = models.CharField(
        max_length = 8,
        unique = True,
        help_text = "IČO účtovnej jednotky",
        db_column="ICO",
    )
    dic = models.CharField(
        max_length = 10,
        blank = True,
        null = True,
        help_text = "DIČ účtovnej jednotky",
        db_column="DIC",
    )
    sid = models.CharField(
        max_length = 5,
        blank = True,
        null = True,
        help_text = "SID účtovnej jednotky",
        db_column="SID",
    )
    nazov_UJ = models.CharField(
        max_length = 500,
        help_text = "Názov účtovnej jednotky",
        db_column="Názov UJ",
    )
    mesto = models.CharField(
        max_length = 200,
        blank = True,
        null = True,
        help_text = "Adresa účtovnej jednotky, mesto",
        db_column="Mesto",
    )
    ulica = models.CharField(
        max_length = 200,
        blank = True,
        null = True,
        help_text = "Adresa účtovnej jednotky, ulica s číslom",
        db_column="Ulica",
    )
    psc = models.CharField(
        max_length = 10,
        blank = True,
        null = True,
        help_text = "Adresa účtovnej jednotky, PSČ",
        db_column="PSČ",
    )
    datum_zalozenia = models.DateField(
        blank = True,
        null = True,
        help_text = "Dátum založenia účtovnej jednotky",
        db_column="Dátum založenia UJ",
    )
    datum_zrusenia = models.DateField(
        blank = True,
        null = True,
        help_text = "Dátum zrušenia účtovnej jednotky",
        db_column="Dátum zrušenia UJ",
    )
    pravna_forma = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód právnej formy",
        db_column="Právna forma",
    )
    sk_NACE = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód SK NACE klasifikácie",
        db_column="NACE",
    )
    velkost_organizacie = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód kategórie veľkosti organizácie",
        db_column="Veľkosť",
    )
    druh_vlastnictva = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód druhu vlastníctva",
        db_column="Vlastníctvo",
    )
    kraj = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Sídlo účtovnej jednotky, kód kraja",
        db_column="Kraj",
    )
    okres = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Sídlo účtovnej jednotky, kód okresu",
        db_column="Okres",
    )
    sidlo = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Sídlo účtovnej jednotky, kód obce alebo mesta",
        db_column="Sídlo",
    )
    konsolidovana = models.BooleanField(
        default = False,
        help_text = "Príznak, či jednotka obsahuje aspoň jednu konsolidovanú účtovnú závierku",
        db_column="Konsolidovaná",
    )
    id_uctovnych_zavierok = models.JSONField(
        default = list,
        help_text = "Zoznam identifikátorov všetkých súvisiacich účtovných závierok",
        db_column="ID UZ",
    )
    id_vyrocnych_sprav = models.JSONField(
        default = list,
        help_text = "Zoznam identifikátorov všetkých súvisiacich výročných správ",
        db_column="ID VS",
    )
    zdroj_dat = models.CharField(
        max_length = 30,
        blank = True,
        null = True,
        help_text = "Kód zdroja, z ktorého pochádzajú dáta",
        db_column="Kód zdroja",
    )
    datum_poslednej_upravy = models.DateField(
        null=True,
        blank=True,
        help_text = "Dátum poslednej úpravy",
        db_column="Dátum a čas kontroly RUZ",
    )

    """
    Represents a debt of company in VSZP and Socialna Poistovna (Life and Social Insurance).
    """
    debt_vszp = models.DecimalField(
        verbose_name="Dlh vo VSZP",
        max_digits = 10,
        decimal_places = 2,
        null = True,
        blank = True,
        help_text = "Dlh vo Všeobecnej zdravotnej poisťovni",
        db_column="Dlh vo VSZP"
    )
    debt_soc_poist = models.DecimalField(
        verbose_name="Dlh v SP",
        max_digits = 10,
        decimal_places = 2,
        null = True,
        blank = True,
        help_text = "Dlh v Sociálnej poisťovni",
        db_column="Dlh v SP"
    )
    last_insurance_debt = models.DateTimeField(
        verbose_name="Posledná kontrola dlhov vo VSZP a SP",
        null = True,
        blank = True,
        help_text = "Dátum a čas poslednej kontroly dlhov v poisťovniach",
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
        db_column="Daňový dlh"
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
        db_column="IČ DPH"
    )
    datum_reg_dph = models.DateField(
        verbose_name="Dátum registrácie DPH",
        null=True,
        blank=True,
        help_text="Dátum registrácie subjektu pre DPH",
        db_column="Dátum registrácie DPH"
    )
    fs_update_date = models.DateTimeField(
        verbose_name="Posledná aktualizácia z FS",
        null=True,
        blank=True,
        help_text="Dátum poslednej aktualizácie dát z FS",
        db_column="Dátum kontroly FS"
    )

    class Meta:
        db_table = "Firmy"

    def __str__(self):
        return self.company
