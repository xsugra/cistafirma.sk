from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0002_alter_company_options"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyFinancialResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(verbose_name="Rok")),
                ("revenue", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, verbose_name="Tržby")),
                ("profit", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, verbose_name="Zisk")),
                ("source", models.CharField(blank=True, default="manual", max_length=30, verbose_name="Zdroj")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Aktualizované")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="financial_results",
                        to="companies.company",
                        verbose_name="Firma",
                    ),
                ),
            ],
            options={
                "db_table": "Company Financial Results",
                "verbose_name": "Hospodársky výsledok",
                "verbose_name_plural": "Hospodárske výsledky",
                "ordering": ["-year"],
                "unique_together": {("company", "year")},
            },
        ),
    ]

