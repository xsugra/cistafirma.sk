from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    """User's notification preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Používateľ',
    )
    email_enabled = models.BooleanField(
        default=True,
        verbose_name='Emailové notifikácie',
    )
    on_debt_change = models.BooleanField(
        default=True,
        verbose_name='Zmena dlhov',
        help_text='Nový dlh alebo zmena výšky dlhu voči VšZP, SP, FS',
    )
    on_status_change = models.BooleanField(
        default=True,
        verbose_name='Zmena statusu firmy',
        help_text='Zrušenie, likvidácia, konkurz',
    )
    on_executive_change = models.BooleanField(
        default=False,
        verbose_name='Zmena štatutárov',
        help_text='Nový konateľ, prokurista, zmena v orgánoch',
    )

    class Meta:
        db_table = 'Notification Preferences'
        verbose_name = 'Notifikačné preferencie'
        verbose_name_plural = 'Notifikačné preferencie'

    def __str__(self):
        return f'Preferences: {self.user.email}'


class NotificationEvent(models.Model):
    """A notification event for a user about a watched company."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Čaká'
        SENDING = 'sending', 'Odosiela sa'
        SENT = 'sent', 'Odoslané'
        FAILED = 'failed', 'Zlyhalo'

    class EventType(models.TextChoices):
        DEBT_CHANGE = 'debt_change', 'Zmena dlhu'
        STATUS_CHANGE = 'status_change', 'Zmena statusu'
        EXECUTIVE_CHANGE = 'executive_change', 'Zmena štatutára'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_events',
        verbose_name='Používateľ',
    )
    company_ico = models.CharField(
        max_length=20,
        verbose_name='IČO firmy',
    )
    company_name = models.CharField(
        max_length=255,
        verbose_name='Názov firmy',
    )
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        verbose_name='Typ udalosti',
    )
    title = models.CharField(
        max_length=255,
        verbose_name='Titulok',
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Detaily',
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Stav odoslania',
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Odoslané',
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Pokusy',
    )
    last_error = models.TextField(
        blank=True,
        default='',
        verbose_name='Posledná chyba',
    )
    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Rezervované workerom',
        help_text='Kedy si worker event vyhradil; staršie ako lease sa automaticky re-claimujú.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Vytvorené',
    )

    class Meta:
        db_table = 'Notification Events'
        verbose_name = 'Notifikačná udalosť'
        verbose_name_plural = 'Notifikačné udalosti'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'[{self.event_type}] {self.title} → {self.user.email}'
