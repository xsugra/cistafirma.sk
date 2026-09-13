from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SyncGapAnalysis(models.Model):
    """
    Model pre ukladanie výsledkov analýzy dier v RUZ ID.
    Pomáha identifikovať chýbajúce záznamy v databáze.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Čaká na analýzu'),
        ('analyzing', 'Analyzuje sa'),
        ('ready', 'Pripravené na opravu'),
        ('repairing', 'Opravuje sa'),
        ('completed', 'Dokončené'),
        ('failed', 'Zlyhalo'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Stav',
    )
    
    # Rozsah analýzy
    analyzed_min_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Minimálne analyzované ID',
    )
    
    analyzed_max_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Maximálne analyzované ID',
    )
    
    # Štatistiky
    total_existing = models.IntegerField(
        default=0,
        verbose_name='Existujúcich firiem v DB',
    )
    
    total_missing = models.IntegerField(
        default=0,
        verbose_name='Chýbajúcich ID',
    )
    
    total_gaps = models.IntegerField(
        default=0,
        verbose_name='Počet dier (rozsahov)',
    )
    
    # JSON pole s rozsahmi dier [(start, end), ...]
    gap_ranges = models.JSONField(
        default=list,
        verbose_name='Rozsahy dier',
        help_text='Zoznam rozsahov chýbajúcich ID: [[start, end], ...]',
    )
    
    # Progress opravy
    repair_progress_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Opravené do ID',
        help_text='Posledné opravené RUZ ID',
    )
    
    repaired_count = models.IntegerField(
        default=0,
        verbose_name='Opravených',
    )
    
    skipped_count = models.IntegerField(
        default=0,
        verbose_name='Preskočených (404/deleted)',
    )
    
    error_count = models.IntegerField(
        default=0,
        verbose_name='Chýb',
    )
    
    # Časové záznamy
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Vytvorené',
    )
    
    analyzed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Analyzované',
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Dokončené',
    )
    
    last_error = models.TextField(
        blank=True,
        default='',
        verbose_name='Posledná chyba',
    )
    
    class Meta:
        verbose_name = 'Analýza dier v RUZ'
        verbose_name_plural = 'Analýzy dier v RUZ'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Analýza {self.created_at.strftime('%d.%m.%Y %H:%M')} - {self.total_missing} chýbajúcich"
    
    def get_missing_ids_iterator(self):
        """
        Generátor, ktorý vracia jednotlivé chýbajúce ID z rozsahov.
        Efektívne pre veľké rozsahy.
        """
        for gap_range in self.gap_ranges:
            start, end = gap_range
            for ruz_id in range(start, end + 1):
                yield ruz_id
    
    def get_remaining_ids_iterator(self):
        """
        Generátor pre zostávajúce ID, ktoré ešte neboli opravené.
        """
        start_from = self.repair_progress_id or 0
        for gap_range in self.gap_ranges:
            start, end = gap_range
            for ruz_id in range(start, end + 1):
                if ruz_id > start_from:
                    yield ruz_id


class SyncProgress(models.Model):
    """
    Model pre sledovanie stavu synchronizácie z RUZ API.
    Umožňuje pokračovať v synchronizácii tam, kde sa skončilo.
    """
    
    SYNC_TYPES = [
        # New entity-specific types
        ('full_companies', 'Full Sync - Firmy (LPO)'),
        ('full_individuals', 'Full Sync - Fyzické osoby (SZCO)'),
        ('incremental_companies', 'Incremental - Firmy (LPO)'),
        ('incremental_individuals', 'Incremental - Fyzické osoby (SZCO)'),
        ('repair_companies', 'Repair - Firmy (LPO)'),
        ('repair_individuals', 'Repair - Fyzické osoby (SZCO)'),
        # Legacy types (for backward compatibility)
        ('full', 'Full Sync'),
        ('incremental', 'Incremental Sync'),
        ('repair', 'Repair Sync'),
    ]
    
    STATUS_CHOICES = [
        ('idle', 'Nečinný'),
        ('running', 'Beží'),
        ('paused', 'Pozastavený'),
        ('completed', 'Dokončený'),
        ('failed', 'Zlyhalo'),
    ]
    
    sync_type = models.CharField(
        max_length=50,
        choices=SYNC_TYPES,
        default='full',
        verbose_name='Typ synchronizácie',
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='idle',
        verbose_name='Stav',
    )
    
    # Sledovanie progresu
    last_processed_ruz_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Posledné spracované RUZ ID',
        help_text='ID poslednej úspešne spracovanej firmy',
    )
    
    zmenene_od = models.DateField(
        null=True,
        blank=True,
        verbose_name='Zmenené od',
        help_text='Dátum od ktorého sa synchronizujú zmeny',
    )
    
    # Štatistiky
    total_processed = models.IntegerField(
        default=0,
        verbose_name='Celkom spracovaných',
    )
    
    total_created = models.IntegerField(
        default=0,
        verbose_name='Nových firiem',
    )
    
    total_updated = models.IntegerField(
        default=0,
        verbose_name='Aktualizovaných',
    )
    
    total_skipped = models.IntegerField(
        default=0,
        verbose_name='Preskočených',
    )
    
    total_errors = models.IntegerField(
        default=0,
        verbose_name='Chýb',
    )
    
    # Časové záznamy
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Spustené',
    )
    
    last_activity = models.DateTimeField(
        auto_now=True,
        verbose_name='Posledná aktivita',
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Dokončené',
    )
    
    # Chybové správy
    last_error = models.TextField(
        blank=True,
        default='',
        verbose_name='Posledná chyba',
    )
    
    # Poznámky
    notes = models.TextField(
        blank=True,
        default='',
        verbose_name='Poznámky',
    )
    
    class Meta:
        verbose_name = 'Stav synchronizácie'
        verbose_name_plural = 'Stavy synchronizácie'
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.get_sync_type_display()} - {self.get_status_display()} ({self.total_processed} firiem)"
    
    def get_progress_percentage(self):
        from core.constants import RUZ_ESTIMATED_COMPANY_COUNT
        if self.total_processed >= RUZ_ESTIMATED_COMPANY_COUNT:
            return 100
        return round((self.total_processed / RUZ_ESTIMATED_COMPANY_COUNT) * 100, 1)
    
    def get_duration(self):
        """Vráti trvanie synchronizácie"""
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        return end_time - self.started_at
    
    def get_rate(self):
        """Vráti rýchlosť spracovania (firiem/hodina)"""
        duration = self.get_duration()
        if not duration or duration.total_seconds() == 0:
            return 0
        hours = duration.total_seconds() / 3600
        return round(self.total_processed / hours, 0)
    
    @classmethod
    def get_or_create_active(cls, sync_type='full'):
        """Získa alebo vytvorí aktívny záznam pre daný typ synchronizácie"""
        # Skúsime nájsť existujúci sync (akýkoľvek stav okrem idle)
        existing = cls.objects.filter(
            sync_type=sync_type,
        ).exclude(status='idle').order_by('-last_activity').first()
        
        if existing:
            return existing, False
        
        # Ak neexistuje žiadny, skúsime nájsť idle
        idle = cls.objects.filter(sync_type=sync_type, status='idle').first()
        if idle:
            return idle, False
        
        # Vytvoríme nový
        return cls.objects.create(
            sync_type=sync_type,
            status='idle'
        ), True
    
    def start(self, zmenene_od=None):
        """Spustí synchronizáciu"""
        self.status = 'running'
        self.started_at = timezone.now()
        if zmenene_od:
            self.zmenene_od = zmenene_od
        self.save()
    
    def pause(self, reason=''):
        """Pozastaví synchronizáciu"""
        self.status = 'paused'
        if reason:
            self.notes = f"Pozastavené: {reason}\n{self.notes}"
        self.save()
    
    def resume(self):
        """Pokračuje v synchronizácii"""
        self.status = 'running'
        self.save()
    
    def complete(self):
        """Označí synchronizáciu ako dokončenú"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def fail(self, error_message=''):
        """Označí synchronizáciu ako zlyhanú"""
        self.status = 'failed'
        self.last_error = error_message
        self.completed_at = timezone.now()
        self.save()
    
    def record_progress(self, ruz_id, created=False, updated=False, skipped=False, error=False):
        """Zaznamená spracovanie jednej firmy"""
        self.last_processed_ruz_id = ruz_id
        self.total_processed += 1
        
        if created:
            self.total_created += 1
        elif updated:
            self.total_updated += 1
        elif skipped:
            self.total_skipped += 1
        
        if error:
            self.total_errors += 1
        
        # Ukladáme len každých 100 záznamov pre efektivitu
        if self.total_processed % 100 == 0:
            self.save(update_fields=[
                'last_processed_ruz_id', 'total_processed', 'total_created',
                'total_updated', 'total_skipped', 'total_errors', 'last_activity'
            ])


class OrsrCompanyProfile(models.Model):
    """
    ORSR profil firmy naviazaný na existujúci Company záznam.
    Ukladá kľúčové polia štruktúrovane + raw sekcie pre robustnosť parsera.
    """

    company = models.OneToOneField(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="orsr_profile",
        verbose_name="Firma",
    )
    # The profile's IČO is written from the ORSR/RPO payload, falling back to
    # `company.ico`; widthed to match. Not unique -- this row is keyed by its
    # `company` OneToOne, so the column is a search aid, not an identity.
    ico = models.CharField(max_length=20, db_index=True, verbose_name="IČO")

    oddiel = models.CharField(max_length=50, blank=True, default="", verbose_name="Oddiel")
    oddiel_type = models.CharField(max_length=10, blank=True, default="", verbose_name="Typ ORSR (Sr/Dr/...)")
    vlozka_cislo = models.CharField(max_length=50, blank=True, default="", verbose_name="Vložka číslo")
    obchodne_meno = models.CharField(max_length=500, blank=True, default="", verbose_name="Obchodné meno")
    sidlo = models.TextField(blank=True, default="", verbose_name="Sídlo")
    den_zapisu = models.DateField(null=True, blank=True, verbose_name="Deň zápisu")
    pravna_forma = models.CharField(max_length=200, blank=True, default="", verbose_name="Právna forma")
    konanie = models.TextField(blank=True, default="", verbose_name="Konanie menom subjektu")
    konanie_menom_spolocnosti = models.TextField(blank=True, default="", verbose_name="Konanie menom spoločnosti")
    vyska_zakladneho_imania = models.TextField(blank=True, default="", verbose_name="Výška základného imania")

    # Polia pre družstvá
    predstavenstvo = models.JSONField(default=list, verbose_name="Predstavenstvo")
    kontrolna_komisia = models.JSONField(default=list, verbose_name="Kontrolná komisia")
    zakladny_clensky_vklad = models.TextField(blank=True, default="", verbose_name="Základný členský vklad")
    zapisovane_zakladne_imanie = models.TextField(blank=True, default="", verbose_name="Zapisované základné imanie")

    predmet_podnikania = models.JSONField(default=list, verbose_name="Predmet podnikania")
    spolocnici = models.JSONField(default=list, verbose_name="Spoločníci")
    vklady_spolocnikov = models.JSONField(default=list, verbose_name="Vklady spoločníkov")
    statutarny_organ = models.JSONField(default=list, verbose_name="Štatutárny orgán")
    prokura = models.JSONField(default=list, verbose_name="Prokúra")
    dalske_pravne_skutocnosti = models.TextField(blank=True, default="", verbose_name="Ďalšie právne skutočnosti")

    orsr_aktualizacia_dat = models.DateField(null=True, blank=True, verbose_name="Dátum aktualizácie údajov ORSR")
    orsr_datum_vypisu = models.DateField(null=True, blank=True, verbose_name="Dátum výpisu ORSR")

    source_url = models.URLField(blank=True, default="", verbose_name="Zdroj URL")
    raw_sections = models.JSONField(default=dict, verbose_name="Raw sekcie ORSR")
    raw_payload = models.JSONField(default=dict, verbose_name="Raw payload")

    last_synced_at = models.DateTimeField(auto_now=True, verbose_name="Posledná synchronizácia")
    fetch_ok = models.BooleanField(default=True, verbose_name="Posledný fetch úspešný")
    last_error = models.TextField(blank=True, default="", verbose_name="Posledná chyba")

    class Meta:
        verbose_name = "ORSR profil firmy"
        verbose_name_plural = "ORSR profily firiem"
        ordering = ["-last_synced_at"]

    def save(self, *args, **kwargs):
        if not self.ico:
            self.ico = self.company.ico

        # Defensive normalization for fields introduced in ORSR schema extension.
        self.oddiel_type = self.oddiel_type or ""
        self.konanie = self.konanie or ""
        self.zakladny_clensky_vklad = self.zakladny_clensky_vklad or ""
        self.zapisovane_zakladne_imanie = self.zapisovane_zakladne_imanie or ""
        self.dalske_pravne_skutocnosti = self.dalske_pravne_skutocnosti or ""
        self.predstavenstvo = self.predstavenstvo or []
        self.kontrolna_komisia = self.kontrolna_komisia or []

        super().save(*args, **kwargs)

    def __str__(self):
        return f"ORSR {self.ico} - {self.obchodne_meno or self.company.nazov_UJ}"


class SyncFocusModeState(models.Model):
    """
    Singleton-style (pk=1) toggle pre "Focus Mode":
    zastaví všetky Celery tasky mimo whitelistu (ORSR + financials)
    a vypne zodpovedajúce PeriodicTask entries v django-celery-beat.
    """

    active = models.BooleanField(default=False, verbose_name='Aktívny')
    snapshot = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Snapshot vypnutých PeriodicTask',
        help_text='Zoznam {"id": int, "enabled": bool} pre obnovu pri deaktivácii.',
    )
    last_revoked = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Naposledy revoknuté tasky',
        help_text='Zoznam {"worker", "name", "id"} z posledného enter_focus_mode volania.',
    )
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name='Aktivované o')
    deactivated_at = models.DateTimeField(null=True, blank=True, verbose_name='Deaktivované o')
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Aktivoval',
    )
    notes = models.TextField(blank=True, default='', verbose_name='Poznámky')

    class Meta:
        verbose_name = 'Focus mode stav'
        verbose_name_plural = 'Focus mode stav'

    def __str__(self):
        return 'Focus mode: ' + ('aktívny' if self.active else 'neaktívny')

    @classmethod
    def load(cls):
        """Load singleton row (pk=1), creating it on first access."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ============================================================================
# Admin overhaul: per-company sync status + structured job tracking + audit log.
# Replaces / augments SyncProgress and SyncGapAnalysis above.
# ============================================================================


class CompanySyncStatus(models.Model):
    """Per-company, per-source sync state.

    One row per (company, source). Used by the new sync_engine to compute
    retry schedules, surface failed companies in admin, and decide which
    companies to refresh in batch tasks.
    """

    SOURCE_RUZ = "ruz"
    SOURCE_ORSR = "orsr"
    SOURCE_FINANCIALS = "financials"
    SOURCE_VSZP = "vszp"
    SOURCE_SOCIAL = "social"
    SOURCE_FS = "fs"
    SOURCE_CHOICES = [
        (SOURCE_RUZ, "RUZ základné údaje"),
        (SOURCE_ORSR, "ORSR profil"),
        (SOURCE_FINANCIALS, "Finančné výkazy"),
        (SOURCE_VSZP, "VšZP dlhy"),
        (SOURCE_SOCIAL, "Sociálna poisťovňa"),
        (SOURCE_FS, "Finančná správa"),
    ]

    ERROR_TYPE_CHOICES = [
        ("", "—"),
        ("http_429", "HTTP 429 (rate limit)"),
        ("http_404", "HTTP 404 (not found)"),
        ("http_5xx", "HTTP 5xx (server error)"),
        ("timeout", "Timeout"),
        ("parse_error", "Parsing chyba"),
        ("network", "Sieťová chyba"),
        ("validation", "Validačná chyba"),
        ("unknown", "Neznáma"),
    ]

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="sync_statuses",
        verbose_name="Firma",
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        verbose_name="Zdroj",
    )

    last_attempted_at = models.DateTimeField(null=True, blank=True, verbose_name="Posledný pokus")
    last_succeeded_at = models.DateTimeField(null=True, blank=True, verbose_name="Posledný úspech")
    last_error = models.TextField(blank=True, default="", verbose_name="Posledná chyba")
    last_error_type = models.CharField(
        max_length=20,
        choices=ERROR_TYPE_CHOICES,
        blank=True,
        default="",
        verbose_name="Typ chyby",
    )
    # What the last attempt had to say about itself, on an *answered* attempt --
    # where `last_error` is empty by construction, because an answered attempt is
    # a success (`FinancialsSyncResult.succeeded`). Without it a company whose
    # statements were present and none of them recordable keeps nothing at all:
    # the result's `detail` is logged and dropped, and `ANSWERED_RETRY_AFTER`
    # pushes the next attempt out a year, so no later run can recover it either
    # (docs/SOURCE_DATA_INTEGRITY.md, "Four causes, one string").
    last_detail = models.TextField(
        blank=True, default="", verbose_name="Detail posledného pokusu"
    )

    # Which revision of the parser produced the rows this attempt wrote. Only
    # `source='financials'` stamps it -- the other five sources have no parser
    # whose vocabulary can change under stored data -- and it is NULL for every
    # attempt made before the field existed.
    #
    # It lives on the *status* row, not only on the result rows, because the
    # status row is what the rotation iterates. A successful read sets
    # `next_retry_at` a year out (`ANSWERED_RETRY_AFTER`), so without a revision
    # here a parser fix could only ever reach companies the rotation happened to
    # revisit -- which is to say almost none. Measured 2026-09-13: the accrual
    # asymmetry collapsed by a factor of 28 (24 323 -> 864) on the companies a
    # re-read reached, and nothing would have reached the rest.
    #
    # `companies_due_for_sync(stale_revision=...)` reads it, so bumping
    # `ruz_financials_sync.PARSER_REVISION` makes every row an older revision
    # wrote eligible again -- through the retry population, which
    # `rotating_batch` already caps at `1 / RETRY_SHARE` of a batch. Bounded by
    # construction: a bump re-reads the corpus over days, it does not flood a
    # queue. See docs/SOURCE_DATA_INTEGRITY.md.
    parser_revision = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False, verbose_name="Revízia parsera"
    )

    consecutive_failures = models.PositiveIntegerField(default=0, verbose_name="Po sebe idúce chyby")
    next_retry_at = models.DateTimeField(null=True, blank=True, verbose_name="Ďalší pokus o")
    is_blocked = models.BooleanField(default=False, verbose_name="Manuálne zablokované")
    blocked_reason = models.TextField(blank=True, default="", verbose_name="Dôvod blokovania")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Stav sync firmy"
        verbose_name_plural = "Stavy sync firiem"
        unique_together = [("company", "source")]
        indexes = [
            models.Index(fields=["source", "last_succeeded_at"], name="reg_css_source_succ_idx"),
            models.Index(fields=["source", "consecutive_failures"], name="reg_css_source_fail_idx"),
            models.Index(fields=["source", "next_retry_at"], name="reg_css_source_retry_idx"),
            models.Index(fields=["is_blocked"], name="reg_css_blocked_idx"),
        ]

    def __str__(self):
        return f"{self.company_id}/{self.source} (failures={self.consecutive_failures})"

    @property
    def is_healthy(self) -> bool:
        return self.consecutive_failures == 0 and self.last_succeeded_at is not None


class SyncJob(models.Model):
    """A single sync run. Replaces SyncProgress with proper per-run tracking.

    Each invocation of a bulk sync (full RUZ, ORSR batch, financial batch,
    insurance check, FS update, manual one-off) creates a SyncJob row.
    """

    JOB_TYPE_CHOICES = [
        ("ruz_full", "RUZ Full Sync"),
        ("ruz_full_firmy", "RUZ Full Sync - Firmy only"),
        ("ruz_full_szco", "RUZ Full Sync - SZCO only"),
        ("ruz_incremental", "RUZ Incremental"),
        ("ruz_repair", "RUZ Repair (gap fill)"),
        ("orsr_batch", "ORSR Batch"),
        ("financials_batch", "Financials Batch"),
        ("insurance_batch", "Insurance Debt Batch"),
        ("fs_update", "Finančná správa"),
        ("manual", "Manuálne (jedna firma)"),
    ]

    STATUS_CHOICES = [
        ("queued", "Vo fronte"),
        ("running", "Beží"),
        ("paused", "Pozastavený"),
        ("completed", "Dokončený"),
        ("failed", "Zlyhalo"),
        ("cancelled", "Zrušený"),
    ]

    TRIGGERED_VIA_CHOICES = [
        ("admin_ui", "Admin UI"),
        ("beat_schedule", "Beat scheduler"),
        ("cli", "CLI / management command"),
        ("api", "API"),
        ("system", "Systém (watchdog, retry)"),
    ]

    job_type = models.CharField(max_length=30, choices=JOB_TYPE_CHOICES, verbose_name="Typ úlohy")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued", verbose_name="Stav")

    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Spustil",
    )
    triggered_via = models.CharField(
        max_length=20,
        choices=TRIGGERED_VIA_CHOICES,
        default="system",
        verbose_name="Spustené cez",
    )
    parameters = models.JSONField(default=dict, blank=True, verbose_name="Parametre")

    total_items = models.PositiveIntegerField(null=True, blank=True, verbose_name="Celkový počet")
    processed_items = models.PositiveIntegerField(default=0, verbose_name="Spracovaných")
    succeeded_items = models.PositiveIntegerField(default=0, verbose_name="Úspešných")
    failed_items = models.PositiveIntegerField(default=0, verbose_name="Chybných")
    skipped_items = models.PositiveIntegerField(default=0, verbose_name="Preskočených")

    queued_at = models.DateTimeField(auto_now_add=True, verbose_name="Vložené do fronty")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Spustené")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Dokončené")
    last_heartbeat = models.DateTimeField(null=True, blank=True, verbose_name="Posledný heartbeat")

    last_error = models.TextField(blank=True, default="", verbose_name="Posledná chyba")
    notes = models.TextField(blank=True, default="", verbose_name="Poznámky")
    celery_task_id = models.CharField(max_length=255, blank=True, default="", verbose_name="Celery task ID")
    concurrency_key = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Kľúč súbežnosti",
    )

    class Meta:
        verbose_name = "Sync úloha"
        verbose_name_plural = "Sync úlohy"
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["status", "job_type"], name="reg_sj_status_type_idx"),
            models.Index(fields=["-queued_at"], name="reg_sj_queued_idx"),
            models.Index(fields=["-started_at"], name="reg_sj_started_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["concurrency_key"],
                condition=Q(
                    concurrency_key="ruz:global",
                    status__in=["queued", "running"],
                ),
                name="reg_one_active_ruz_job",
            ),
        ]

    def __str__(self):
        return f"{self.get_job_type_display()} #{self.pk} ({self.get_status_display()})"

    @property
    def progress_percentage(self) -> float:
        if not self.total_items:
            return 0.0
        return round((self.processed_items / self.total_items) * 100, 1)

    @property
    def duration_seconds(self) -> float | None:
        if not self.started_at:
            return None
        end = self.completed_at or timezone.now()
        return (end - self.started_at).total_seconds()

    @property
    def items_per_hour(self) -> float:
        dur = self.duration_seconds
        if not dur or dur <= 0:
            return 0.0
        return round(self.processed_items / (dur / 3600), 1)

    def heartbeat(self):
        """Bump last_heartbeat without saving the entire row."""
        SyncJob.objects.filter(pk=self.pk).update(last_heartbeat=timezone.now())


# `SyncJobItem` used to live here: a per-item record inside a `SyncJob`, written
# by `sync_engine.record_item` and read by the `sync/jobs/{pk}/items/` endpoint
# and `retry-failed`. Both are gone, because nothing ever wrote one -- the only
# caller was the `tracked_sync_task` decorator, which was applied to no task, so
# the table never held a row and `retry-failed` always retried an empty list.
# A per-company trace is not missing from the system, only from the `SyncJob`:
# `CompanySyncStatus` carries one row per company per source, written by
# `ruz_financials_sync.sync_company_and_record`, `record_ruz_date_outcome` and
# `record_orsr_outcome`.


# ============================================================================
# INDIVIDUAL ENTITY MODEL - Natural persons and SZCO (without ORSR profile)
# ============================================================================

class IndividualEntity(models.Model):
    """
    Represents a natural person or SZCO (individual business activity) from RUZ API.
    Mirror of Company model, but without ORSR profile (natural persons have no business register).

    Legal forms for SZCO:
      100-110: Natural persons (entrepreneurs, free professions, independent farmers...)
      422: Foreign natural person
    """
    ruz_id = models.IntegerField(
        unique=True,
        help_text="Identifikátor účtovnej jednotky z RUZ API",
        db_column="RUZ ID",
    )
    # Widened with `Company.ico` and for the same reason -- see the note there.
    # An SZCO cannot currently carry a 12-character IČO, but the two tables are
    # written by one code path and a width that differs between them is the kind
    # of asymmetry that only shows up as a `DataError` on the rarer of the two.
    ico = models.CharField(
        max_length=20,
        unique=True,
        help_text="IČO fyzickej osoby",
        db_column="ICO",
    )
    dic = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="DIČ fyzickej osoby",
        db_column="DIC",
    )
    sid = models.CharField(
        max_length=5,
        blank=True,
        null=True,
        help_text="SID fyzickej osoby",
        db_column="SID",
    )
    nazov_UJ = models.CharField(
        max_length=500,
        help_text="Názov/meno fyzickej osoby",
        db_column="Názov UJ",
    )
    mesto = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Adresa, mesto",
        db_column="Mesto",
    )
    ulica = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Adresa, ulica s číslom",
        db_column="Ulica",
    )
    psc = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text="Adresa, PSČ",
        db_column="PSČ",
    )
    datum_zalozenia = models.DateField(
        blank=True,
        null=True,
        help_text="Dátum založenia podnikania",
        db_column="Dátum založenia UJ",
    )
    datum_zrusenia = models.DateField(
        blank=True,
        null=True,
        help_text="Dátum zrušenia podnikania",
        db_column="Dátum zrušenia UJ",
    )
    pravna_forma = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Kód právnej formy (100-110, 422)",
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
        help_text="Kód kategórie veľkosti",
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
        help_text="Sídlo, kód kraja",
        db_column="Kraj",
    )
    okres = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Sídlo, kód okresu",
        db_column="Okres",
    )
    sidlo = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Sídlo, kód obce alebo mesta",
        db_column="Sídlo",
    )
    konsolidovana = models.BooleanField(
        default=False,
        help_text="Príznak konsolidovanej účtovnej závierky",
        db_column="Konsolidovaná",
    )
    uses_ifrs = models.BooleanField(
        default=False,
        help_text="Fyzická osoba účtuje podľa IFRS",
        db_column="Používa IFRS",
    )
    id_uctovnych_zavierok = models.JSONField(
        default=list,
        help_text="Zoznam ID účtovných závierok",
        db_column="ID UZ",
    )
    id_vyrocnych_sprav = models.JSONField(
        default=list,
        help_text="Zoznam ID výročných správ",
        db_column="ID VS",
    )
    zdroj_dat = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Kód zdroja dát",
        db_column="Kód zdroja",
    )
    datum_poslednej_upravy = models.DateField(
        null=True,
        blank=True,
        help_text="Dátum poslednej úpravy",
        db_column="Dátum a čas kontroly RUZ",
    )

    # Debt fields
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
        verbose_name="Posledná kontrola dlhov",
        null=True,
        blank=True,
        help_text="Dátum poslednej kontroly dlhov v poisťovniach",
        db_column="Dátum a čas kontroly VSZP/SP"
    )

    # Tax fields (FS - Financna sprava)
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
        help_text="Je platiteľ DPH?",
        db_column="Platiteľ DPH",
    )
    ic_dph = models.CharField(
        verbose_name="IČ DPH",
        max_length=20,
        null=True,
        blank=True,
        help_text="Identifikačné číslo pre DPH",
        db_column="IČ DPH",
    )
    datum_reg_dph = models.DateField(
        verbose_name="Dátum registrácie DPH",
        null=True,
        blank=True,
        help_text="Dátum registrácie pre DPH",
        db_column="Dátum registrácie DPH",
    )
    bank_accounts = models.JSONField(
        verbose_name="Bankové účty",
        default=list,
        blank=True,
        help_text="Zoznam bankových účtov",
        db_column="IBANs",
    )
    vat_deleted_date = models.DateField(
        verbose_name="Dátum výmazu z DPH",
        null=True,
        blank=True,
        help_text="Dátum výmazu zo zoznamu DPH",
        db_column="Dátum výmazu DPH",
    )
    vat_deleted_reason = models.CharField(
        verbose_name="Dôvod výmazu z DPH",
        max_length=100,
        null=True,
        blank=True,
        help_text="Dôvod výmazu",
        db_column="Dôvod výmazu DPH",
    )
    tax_reliability = models.CharField(
        verbose_name="Index daňovej spoľahlivosti",
        max_length=50,
        null=True,
        blank=True,
        help_text="Index spoľahlivosti z FS",
        db_column="Index daňovej spoľahlivosti",
    )
    fs_update_date = models.DateTimeField(
        verbose_name="Posledná aktualizácia z FS",
        null=True,
        blank=True,
        help_text="Dátum aktualizácie z FS",
        db_column="Dátum kontroly FS",
    )

    class Meta:
        db_table = "Individual Entities"
        verbose_name = "Fyzická osoba/SZCO"
        verbose_name_plural = "Fyzické osoby/SZCO"
        ordering = ['-datum_poslednej_upravy', 'nazov_UJ']
        indexes = [
            models.Index(fields=['mesto'], name='individual_mesto_idx'),
            models.Index(fields=['psc'], name='individual_psc_idx'),
            models.Index(fields=['kraj'], name='individual_kraj_idx'),
            models.Index(fields=['sk_NACE'], name='individual_nace_idx'),
            models.Index(fields=['pravna_forma'], name='individual_pravna_forma_idx'),
            models.Index(fields=['velkost_organizacie'], name='individual_velkost_idx'),
            models.Index(fields=['datum_zalozenia'], name='individual_datum_zaloz_idx'),
            models.Index(fields=['debt_vszp'], name='individual_debt_vszp_idx'),
            models.Index(fields=['debt_soc_poist'], name='individual_debt_sp_idx'),
            models.Index(fields=['tax_debt'], name='individual_tax_debt_idx'),
        ]

    def __str__(self):
        return self.nazov_UJ


class AuditLog(models.Model):
    """Append-only log of admin actions for accountability and debugging."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Aktér",
    )
    action = models.CharField(
        max_length=80,
        verbose_name="Akcia",
        help_text="napr. 'sync.trigger', 'company.update', 'user.deactivate'",
    )
    target_type = models.CharField(max_length=40, blank=True, default="", verbose_name="Typ cieľa")
    target_id = models.CharField(max_length=64, blank=True, default="", verbose_name="ID cieľa")
    payload = models.JSONField(default=dict, blank=True, verbose_name="Payload")

    method = models.CharField(max_length=10, blank=True, default="", verbose_name="HTTP metóda")
    path = models.CharField(max_length=255, blank=True, default="", verbose_name="URL cesta")
    status_code = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="HTTP status")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP adresa")
    user_agent = models.TextField(blank=True, default="", verbose_name="User agent")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Vytvorené")

    class Meta:
        verbose_name = "Audit log"
        verbose_name_plural = "Audit log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="reg_audit_created_idx"),
            models.Index(fields=["actor", "-created_at"], name="reg_audit_actor_idx"),
            models.Index(fields=["action", "-created_at"], name="reg_audit_action_idx"),
            models.Index(fields=["target_type", "target_id"], name="reg_audit_target_idx"),
        ]

    def __str__(self):
        actor = self.actor.email if self.actor_id else "system"
        return f"{actor} → {self.action} [{self.target_type}:{self.target_id}]"
