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
    )
    ico = models.CharField(
        max_length = 8,
        unique = True,
        help_text = "IČO účtovnej jednotky",
    )
    dic = models.CharField(
        max_length = 10,
        blank = True,
        null = True,
        help_text = "DIČ účtovnej jednotky",
    )
    sid = models.CharField(
        max_length = 5,
        blank = True,
        null = True,
        help_text = "SID účtovnej jednotky",
    )
    nazovUJ = models.CharField(
        max_length = 500,
        help_text = "Názov účtovnej jednotky",
    )
    mesto = models.CharField(
        max_length = 200,
        blank = True,
        null = True,
        help_text = "Adresa účtovnej jednotky, mesto",
    )
    ulica = models.CharField(
        max_length = 200,
        blank = True,
        null = True,
        help_text = "Adresa účtovnej jednotky, ulica s číslom",
    )
    psc = models.CharField(
        max_length = 10,
        blank = True,
        null = True,
        help_text = "Adresa účtovnej jednotky, PSČ",
    )
    datumZalozenia = models.DateField(
        blank = True,
        null = True,
        help_text = "Dátum založenia účtovnej jednotky",
    )
    datumZrusenia = models.DateField(
        blank = True,
        null = True,
        help_text = "Dátum zrušenia účtovnej jednotky",
    )
    pravnaForma = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód právnej formy",
    )
    skNace = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód SK NACE klasifikácie",
    )
    velkostOrganizacie = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód kategórie veľkosti organizácie",
    )
    druhVlastnictva = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Kód druhu vlastníctva",
    )
    kraj = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Sídlo účtovnej jednotky, kód kraja",
    )
    okres = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Sídlo účtovnej jednotky, kód okresu",
    )
    sidlo = models.CharField(
        max_length = 100,
        blank = True,
        null = True,
        help_text = "Sídlo účtovnej jednotky, kód obce alebo mesta",
    )
    konsolidovana = models.BooleanField(
        default = False,
        help_text = "Príznak, či jednotka obsahuje aspoň jednu konsolidovanú účtovnú závierku",
    )
    idUctovnychZavierok = models.JSONField(
        default = list,
        help_text = "Zoznam identifikátorov všetkých súvisiacich účtovných závierok",
    )
    idVyrocnychSprav = models.JSONField(
        default = list,
        help_text = "Zoznam identifikátorov všetkých súvisiacich výročných správ",
    )
    zdrojDat = models.CharField(
        max_length = 30,
        blank = True,
        null = True,
        help_text = "Kód zdroja, z ktorého pochádzajú dáta",
    )
    datumPoslednejUpravy = models.DateField(
        help_text = "Dátum poslednej úpravy",
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
    )
    debt_soc_poist = models.DecimalField(
        verbose_name="Dlh v SP",
        max_digits = 10,
        decimal_places = 2,
        null = True,
        blank = True,
        help_text = "Dlh v Sociálnej poisťovni",
    )
    last_insurance_debt = models.DateTimeField(
        verbose_name="Posledná kontrola dlhov vo VSZP a SP",
        null = True,
        blank = True,
        help_text = "Dátum a čas poslednej kontroly dlhov v poisťovniach",
    )

    tax_debt = models.DecimalField(
        verbose_name="Daňový dlh",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Dlh na daniach z Finančnej správy",
    )
    fs_update_date = models.DateTimeField(
        verbose_name="Posledná aktualizácia z FS",
        null=True,
        blank=True,
        help_text="Dátum poslednej aktualizácie dát z Finančnej správy",
    )

    def __str__(self):
        return self.nazovUJ
