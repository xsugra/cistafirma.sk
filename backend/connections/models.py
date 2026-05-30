import re
import unicodedata

from django.db import models


def compute_fingerprint(name: str, address: str = "", person_ico: str = "") -> str:
    if person_ico and person_ico.strip():
        return f"ico:{person_ico.strip()}"

    normalized = unicodedata.normalize("NFKD", name.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"\s+", " ", normalized).strip()

    addr_part = ""
    if address:
        addr_normalized = unicodedata.normalize("NFKD", address.lower())
        addr_normalized = "".join(c for c in addr_normalized if not unicodedata.combining(c))
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
    is_active = models.BooleanField(default=True, verbose_name="Aktívna")
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
