# Generated manually for persisted admin saved filters.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedCompanyFilter",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("name", models.CharField(max_length=160, verbose_name="Názov filtra")),
                ("description", models.TextField(blank=True, default="", verbose_name="Popis")),
                ("filters", models.JSONField(default=dict, verbose_name="Parametre filtra")),
                ("is_favorite", models.BooleanField(default=False, verbose_name="Obľúbený")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Vytvorené")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Aktualizované")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="saved_company_filters",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Používateľ",
                    ),
                ),
            ],
            options={
                "verbose_name": "Uložený filter firiem",
                "verbose_name_plural": "Uložené filtre firiem",
                "ordering": ["-is_favorite", "name"],
                "unique_together": {("user", "name")},
            },
        ),
    ]


