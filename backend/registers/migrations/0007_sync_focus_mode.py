from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("registers", "0006_backfill_orsr_extended_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncFocusModeState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active", models.BooleanField(default=False, verbose_name="Aktívny")),
                (
                    "snapshot",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text='Zoznam {"id": int, "enabled": bool} pre obnovu pri deaktivácii.',
                        verbose_name="Snapshot vypnutých PeriodicTask",
                    ),
                ),
                (
                    "last_revoked",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text='Zoznam {"worker", "name", "id"} z posledného enter_focus_mode volania.',
                        verbose_name="Naposledy revoknuté tasky",
                    ),
                ),
                ("activated_at", models.DateTimeField(blank=True, null=True, verbose_name="Aktivované o")),
                ("deactivated_at", models.DateTimeField(blank=True, null=True, verbose_name="Deaktivované o")),
                (
                    "activated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Aktivoval",
                    ),
                ),
                ("notes", models.TextField(blank=True, default="", verbose_name="Poznámky")),
            ],
            options={
                "verbose_name": "Focus mode stav",
                "verbose_name_plural": "Focus mode stav",
            },
        ),
    ]
