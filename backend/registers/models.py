from django.db import models
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
        max_length=20,
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
        """Odhadovaný progress v percentách (cca 400000 firiem v RUZ)"""
        estimated_total = 400000
        if self.total_processed >= estimated_total:
            return 100
        return round((self.total_processed / estimated_total) * 100, 1)
    
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
    ico = models.CharField(max_length=8, db_index=True, verbose_name="IČO")

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
