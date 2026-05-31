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
    sent_email = models.BooleanField(
        default=False,
        verbose_name='Email odoslaný',
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
            models.Index(fields=['sent_email', '-created_at']),
        ]

    def __str__(self):
        return f'[{self.event_type}] {self.title} → {self.user.email}'
