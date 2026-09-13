import re
import unicodedata

from django.db import models


def strip_diacritics(text: str) -> str:
    """Lowercase, decompose, and drop the combining marks.

    Slovak diacritics are combining marks under NFKD, so this turns `Kováč`
    into `kovac` -- and `ď`, `ľ`, `ť` into `d`, `l`, `t` rather than losing them
    the way a hand-written translation table would.
    """
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize_name(name: str, title: str = "") -> str:
    """The searchable form of a person's name.

    The title is folded in rather than dropped, because the register keeps
    `Miroslav Trnka` and `Ing. Miroslav Trnka` as separate records and a reader
    typing either should reach the same person. Whitespace is collapsed so a
    substring match cannot be broken by a double space in the source.
    """
    return re.sub(r"\s+", " ", strip_diacritics(f"{title} {name}")).strip()


def compute_fingerprint(name: str, address: str = "", person_ico: str = "") -> str:
    if person_ico and person_ico.strip():
        return f"ico:{person_ico.strip()}"

    normalized = re.sub(r"\s+", " ", strip_diacritics(name)).strip()

    addr_part = ""
    if address:
        addr_normalized = strip_diacritics(address)
        parts = [p.strip() for p in addr_normalized.replace("\n", ",").split(",") if p.strip()]
        for part in reversed(parts):
            if len(part) > 2 and not part.isdigit():
                addr_part = part[:40]
                break

    return f"name:{normalized}|addr:{addr_part}"


class Person(models.Model):
    fingerprint = models.CharField(
        max_length=255, unique=True, db_index=True, verbose_name="Fingerprint"
    )
    name = models.CharField(max_length=500, verbose_name="Meno")
    name_normalized = models.CharField(
        max_length=700,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Meno bez diakritiky",
        help_text="`title` + `name`, diacritics stripped, for searching.",
    )
    title = models.CharField(max_length=100, blank=True, default="", verbose_name="Titul")
    address = models.TextField(blank=True, default="", verbose_name="Adresa")
    person_ico = models.CharField(
        max_length=20, blank=True, default="", db_index=True, verbose_name="IČO osoby"
    )
    is_legal_entity = models.BooleanField(default=False, verbose_name="Právnická osoba")
    linked_company = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="as_person",
        verbose_name="Prepojená firma",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Osoba"
        verbose_name_plural = "Osoby"
        indexes = [
            models.Index(fields=["name"]),
        ]

    def save(self, *args, **kwargs):
        """Keep `name_normalized` in step with the two fields it is built from.

        Derived here rather than at each call site because there are several --
        the ORSR extractor, the RPO extractor, the populate command -- and a row
        whose searchable form is stale is invisible to search while still
        looking perfectly fine in the database.
        """
        self.name_normalized = normalize_name(self.name, self.title)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"name_normalized"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PersonCompanyRelation(models.Model):
    class RoleType(models.TextChoices):
        KONATEL = "konatel", "Konateľ"
        SPOLOCNIK = "spolocnik", "Spoločník"
        PROKURISTA = "prokurista", "Prokurista"
        CLEN_PREDSTAVENSTVA = "clen_predstavenstva", "Člen predstavenstva"
        PREDSEDA_PREDSTAVENSTVA = "predseda_predstavenstva", "Predseda predstavenstva"
        CLEN_DOZORNEJ_RADY = "clen_dozornej_rady", "Člen dozornej rady"
        CLEN_KONTROLNEJ_KOMISIE = "clen_kontrolnej_komisie", "Člen kontrolnej komisie"
        AKCIONAR = "akcionar", "Akcionár"
        RIADITEL = "riaditel", "Riaditeľ"
        INE = "ine", "Iné"

    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="company_relations"
    )
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="person_relations"
    )
    role = models.CharField(
        max_length=50, choices=RoleType.choices, default=RoleType.INE, verbose_name="Rola"
    )
    role_display = models.CharField(
        max_length=200, blank=True, default="", verbose_name="Pôvodný text roly"
    )
    vznik_funkcie = models.DateField(null=True, blank=True, verbose_name="Vznik funkcie")
    zanik_funkcie = models.DateField(null=True, blank=True, verbose_name="Zánik funkcie")
    is_active = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Aktívna",
        help_text=(
            "True/False = the source states it; null = the function's history "
            "was never read for this company, so we do not know."
        ),
    )
    source = models.CharField(max_length=20, default="orsr", verbose_name="Zdroj")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prepojenie osoba–firma"
        verbose_name_plural = "Prepojenia osoba–firma"
        unique_together = [("person", "company", "role", "vznik_funkcie")]
        indexes = [
            models.Index(fields=["company", "is_active"]),
            models.Index(fields=["person", "is_active"]),
        ]

    def __str__(self):
        return f"{self.person.name} → {self.company.nazov_UJ} ({self.get_role_display()})"
