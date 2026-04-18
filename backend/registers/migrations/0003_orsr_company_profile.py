from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0002_alter_company_options"),
        ("registers", "0002_add_sync_gap_analysis"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrsrCompanyProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ico", models.CharField(db_index=True, max_length=8, verbose_name="IČO")),
                ("oddiel", models.CharField(blank=True, default="", max_length=50, verbose_name="Oddiel")),
                ("vlozka_cislo", models.CharField(blank=True, default="", max_length=50, verbose_name="Vložka číslo")),
                ("obchodne_meno", models.CharField(blank=True, default="", max_length=500, verbose_name="Obchodné meno")),
                ("sidlo", models.TextField(blank=True, default="", verbose_name="Sídlo")),
                ("den_zapisu", models.DateField(blank=True, null=True, verbose_name="Deň zápisu")),
                ("pravna_forma", models.CharField(blank=True, default="", max_length=200, verbose_name="Právna forma")),
                ("konanie_menom_spolocnosti", models.TextField(blank=True, default="", verbose_name="Konanie menom spoločnosti")),
                ("vyska_zakladneho_imania", models.TextField(blank=True, default="", verbose_name="Výška základného imania")),
                ("predmet_podnikania", models.JSONField(default=list, verbose_name="Predmet podnikania")),
                ("spolocnici", models.JSONField(default=list, verbose_name="Spoločníci")),
                ("vklady_spolocnikov", models.JSONField(default=list, verbose_name="Vklady spoločníkov")),
                ("statutarny_organ", models.JSONField(default=list, verbose_name="Štatutárny orgán")),
                ("orsr_aktualizacia_dat", models.DateField(blank=True, null=True, verbose_name="Dátum aktualizácie údajov ORSR")),
                ("orsr_datum_vypisu", models.DateField(blank=True, null=True, verbose_name="Dátum výpisu ORSR")),
                ("source_url", models.URLField(blank=True, default="", verbose_name="Zdroj URL")),
                ("raw_sections", models.JSONField(default=dict, verbose_name="Raw sekcie ORSR")),
                ("raw_payload", models.JSONField(default=dict, verbose_name="Raw payload")),
                ("last_synced_at", models.DateTimeField(auto_now=True, verbose_name="Posledná synchronizácia")),
                ("fetch_ok", models.BooleanField(default=True, verbose_name="Posledný fetch úspešný")),
                ("last_error", models.TextField(blank=True, default="", verbose_name="Posledná chyba")),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orsr_profile",
                        to="companies.company",
                        verbose_name="Firma",
                    ),
                ),
            ],
            options={
                "verbose_name": "ORSR profil firmy",
                "verbose_name_plural": "ORSR profily firiem",
                "ordering": ["-last_synced_at"],
            },
        ),
    ]


