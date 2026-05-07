"""Admin overhaul migration.

Adds:
  - CompanySyncStatus (per-company, per-source sync state)
  - SyncJob (replaces SyncProgress's role of run-tracking)
  - SyncJobItem (per-item dead-letter queue)
  - AuditLog (append-only admin action log)

Includes a data-migration step that seeds CompanySyncStatus rows from existing
OrsrCompanyProfile records and Company.last_insurance_debt timestamps so that
the new admin UI shows accurate "last synced" data on day one.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_company_sync_status(apps, schema_editor):
    Company = apps.get_model("companies", "Company")
    CompanySyncStatus = apps.get_model("registers", "CompanySyncStatus")
    OrsrCompanyProfile = apps.get_model("registers", "OrsrCompanyProfile")
    CompanyFinancialResult = apps.get_model("companies", "CompanyFinancialResult")

    # Seed ORSR statuses from existing profiles.
    bulk = []
    for profile in OrsrCompanyProfile.objects.iterator(chunk_size=2000):
        bulk.append(
            CompanySyncStatus(
                company_id=profile.company_id,
                source="orsr",
                last_attempted_at=profile.last_synced_at,
                last_succeeded_at=profile.last_synced_at if profile.fetch_ok else None,
                last_error=profile.last_error or "",
                last_error_type="" if profile.fetch_ok else "unknown",
                consecutive_failures=0 if profile.fetch_ok else 1,
            )
        )
        if len(bulk) >= 1000:
            CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)
            bulk = []
    if bulk:
        CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)

    # Seed insurance status from Company.last_insurance_debt.
    bulk = []
    for company in Company.objects.exclude(last_insurance_debt__isnull=True).only(
        "id", "last_insurance_debt"
    ).iterator(chunk_size=2000):
        for source in ("vszp", "social"):
            bulk.append(
                CompanySyncStatus(
                    company_id=company.id,
                    source=source,
                    last_attempted_at=company.last_insurance_debt,
                    last_succeeded_at=company.last_insurance_debt,
                )
            )
        if len(bulk) >= 1000:
            CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)
            bulk = []
    if bulk:
        CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)

    # Seed financials status from latest CompanyFinancialResult.updated_at.
    try:
        from django.db.models import Max
        bulk = []
        agg = (
            CompanyFinancialResult.objects.values("company_id")
            .annotate(latest=Max("updated_at"))
            .iterator(chunk_size=2000)
        )
        for row in agg:
            bulk.append(
                CompanySyncStatus(
                    company_id=row["company_id"],
                    source="financials",
                    last_attempted_at=row["latest"],
                    last_succeeded_at=row["latest"],
                )
            )
            if len(bulk) >= 1000:
                CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)
                bulk = []
        if bulk:
            CompanySyncStatus.objects.bulk_create(bulk, ignore_conflicts=True)
    except Exception:
        # If CompanyFinancialResult isn't available yet, skip — non-critical.
        pass


def unseed_company_sync_status(apps, schema_editor):
    CompanySyncStatus = apps.get_model("registers", "CompanySyncStatus")
    CompanySyncStatus.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0003_companyfinancialresult"),
        ("registers", "0007_sync_focus_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanySyncStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("ruz", "RUZ základné údaje"),
                            ("orsr", "ORSR profil"),
                            ("financials", "Finančné výkazy"),
                            ("vszp", "VšZP dlhy"),
                            ("social", "Sociálna poisťovňa"),
                            ("fs", "Finančná správa"),
                        ],
                        max_length=20,
                        verbose_name="Zdroj",
                    ),
                ),
                ("last_attempted_at", models.DateTimeField(blank=True, null=True, verbose_name="Posledný pokus")),
                ("last_succeeded_at", models.DateTimeField(blank=True, null=True, verbose_name="Posledný úspech")),
                ("last_error", models.TextField(blank=True, default="", verbose_name="Posledná chyba")),
                (
                    "last_error_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "—"),
                            ("http_429", "HTTP 429 (rate limit)"),
                            ("http_404", "HTTP 404 (not found)"),
                            ("http_5xx", "HTTP 5xx (server error)"),
                            ("timeout", "Timeout"),
                            ("parse_error", "Parsing chyba"),
                            ("network", "Sieťová chyba"),
                            ("validation", "Validačná chyba"),
                            ("unknown", "Neznáma"),
                        ],
                        default="",
                        max_length=20,
                        verbose_name="Typ chyby",
                    ),
                ),
                ("consecutive_failures", models.PositiveIntegerField(default=0, verbose_name="Po sebe idúce chyby")),
                ("next_retry_at", models.DateTimeField(blank=True, null=True, verbose_name="Ďalší pokus o")),
                ("is_blocked", models.BooleanField(default=False, verbose_name="Manuálne zablokované")),
                ("blocked_reason", models.TextField(blank=True, default="", verbose_name="Dôvod blokovania")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_statuses",
                        to="companies.company",
                        verbose_name="Firma",
                    ),
                ),
            ],
            options={
                "verbose_name": "Stav sync firmy",
                "verbose_name_plural": "Stavy sync firiem",
                "unique_together": {("company", "source")},
            },
        ),
        migrations.AddIndex(
            model_name="companysyncstatus",
            index=models.Index(fields=["source", "last_succeeded_at"], name="reg_css_source_succ_idx"),
        ),
        migrations.AddIndex(
            model_name="companysyncstatus",
            index=models.Index(fields=["source", "consecutive_failures"], name="reg_css_source_fail_idx"),
        ),
        migrations.AddIndex(
            model_name="companysyncstatus",
            index=models.Index(fields=["source", "next_retry_at"], name="reg_css_source_retry_idx"),
        ),
        migrations.AddIndex(
            model_name="companysyncstatus",
            index=models.Index(fields=["is_blocked"], name="reg_css_blocked_idx"),
        ),
        migrations.CreateModel(
            name="SyncJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "job_type",
                    models.CharField(
                        choices=[
                            ("ruz_full", "RUZ Full Sync"),
                            ("ruz_incremental", "RUZ Incremental"),
                            ("ruz_repair", "RUZ Repair (gap fill)"),
                            ("orsr_batch", "ORSR Batch"),
                            ("financials_batch", "Financials Batch"),
                            ("insurance_batch", "Insurance Debt Batch"),
                            ("fs_update", "Finančná správa"),
                            ("manual", "Manuálne (jedna firma)"),
                        ],
                        max_length=30,
                        verbose_name="Typ úlohy",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Vo fronte"),
                            ("running", "Beží"),
                            ("paused", "Pozastavený"),
                            ("completed", "Dokončený"),
                            ("failed", "Zlyhalo"),
                            ("cancelled", "Zrušený"),
                        ],
                        default="queued",
                        max_length=20,
                        verbose_name="Stav",
                    ),
                ),
                (
                    "triggered_via",
                    models.CharField(
                        choices=[
                            ("admin_ui", "Admin UI"),
                            ("beat_schedule", "Beat scheduler"),
                            ("cli", "CLI / management command"),
                            ("api", "API"),
                            ("system", "Systém (watchdog, retry)"),
                        ],
                        default="system",
                        max_length=20,
                        verbose_name="Spustené cez",
                    ),
                ),
                ("parameters", models.JSONField(blank=True, default=dict, verbose_name="Parametre")),
                ("total_items", models.PositiveIntegerField(blank=True, null=True, verbose_name="Celkový počet")),
                ("processed_items", models.PositiveIntegerField(default=0, verbose_name="Spracovaných")),
                ("succeeded_items", models.PositiveIntegerField(default=0, verbose_name="Úspešných")),
                ("failed_items", models.PositiveIntegerField(default=0, verbose_name="Chybných")),
                ("skipped_items", models.PositiveIntegerField(default=0, verbose_name="Preskočených")),
                ("queued_at", models.DateTimeField(auto_now_add=True, verbose_name="Vložené do fronty")),
                ("started_at", models.DateTimeField(blank=True, null=True, verbose_name="Spustené")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="Dokončené")),
                ("last_heartbeat", models.DateTimeField(blank=True, null=True, verbose_name="Posledný heartbeat")),
                ("last_error", models.TextField(blank=True, default="", verbose_name="Posledná chyba")),
                ("notes", models.TextField(blank=True, default="", verbose_name="Poznámky")),
                ("celery_task_id", models.CharField(blank=True, default="", max_length=255, verbose_name="Celery task ID")),
                (
                    "triggered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Spustil",
                    ),
                ),
            ],
            options={
                "verbose_name": "Sync úloha",
                "verbose_name_plural": "Sync úlohy",
                "ordering": ["-queued_at"],
            },
        ),
        migrations.AddIndex(
            model_name="syncjob",
            index=models.Index(fields=["status", "job_type"], name="reg_sj_status_type_idx"),
        ),
        migrations.AddIndex(
            model_name="syncjob",
            index=models.Index(fields=["-queued_at"], name="reg_sj_queued_idx"),
        ),
        migrations.AddIndex(
            model_name="syncjob",
            index=models.Index(fields=["-started_at"], name="reg_sj_started_idx"),
        ),
        migrations.CreateModel(
            name="SyncJobItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("item_key", models.CharField(help_text="ICO alebo RUZ ID", max_length=64, verbose_name="Kľúč")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Čaká"),
                            ("running", "Spracováva sa"),
                            ("success", "Úspech"),
                            ("failed", "Zlyhalo"),
                            ("skipped", "Preskočené"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                (
                    "error_type",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "—"),
                            ("http_429", "HTTP 429 (rate limit)"),
                            ("http_404", "HTTP 404 (not found)"),
                            ("http_5xx", "HTTP 5xx (server error)"),
                            ("timeout", "Timeout"),
                            ("parse_error", "Parsing chyba"),
                            ("network", "Sieťová chyba"),
                            ("validation", "Validačná chyba"),
                            ("unknown", "Neznáma"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="companies.company",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="registers.syncjob",
                    ),
                ),
            ],
            options={
                "verbose_name": "Položka sync úlohy",
                "verbose_name_plural": "Položky sync úloh",
            },
        ),
        migrations.AddIndex(
            model_name="syncjobitem",
            index=models.Index(fields=["job", "status"], name="reg_sji_job_status_idx"),
        ),
        migrations.AddIndex(
            model_name="syncjobitem",
            index=models.Index(fields=["status", "company"], name="reg_sji_status_comp_idx"),
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        help_text="napr. 'sync.trigger', 'company.update', 'user.deactivate'",
                        max_length=80,
                        verbose_name="Akcia",
                    ),
                ),
                ("target_type", models.CharField(blank=True, default="", max_length=40, verbose_name="Typ cieľa")),
                ("target_id", models.CharField(blank=True, default="", max_length=64, verbose_name="ID cieľa")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="Payload")),
                ("method", models.CharField(blank=True, default="", max_length=10, verbose_name="HTTP metóda")),
                ("path", models.CharField(blank=True, default="", max_length=255, verbose_name="URL cesta")),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="HTTP status")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP adresa")),
                ("user_agent", models.TextField(blank=True, default="", verbose_name="User agent")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Vytvorené")),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Aktér",
                    ),
                ),
            ],
            options={
                "verbose_name": "Audit log",
                "verbose_name_plural": "Audit log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["-created_at"], name="reg_audit_created_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["actor", "-created_at"], name="reg_audit_actor_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["action", "-created_at"], name="reg_audit_action_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["target_type", "target_id"], name="reg_audit_target_idx"),
        ),
        migrations.RunPython(seed_company_sync_status, reverse_code=unseed_company_sync_status),
    ]
