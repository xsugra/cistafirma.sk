from django.contrib import admin
from django.db.models import Q
from django.utils import timezone

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
except ImportError:
    from django.contrib.admin import ModelAdmin as UnfoldModelAdmin

from .models import NotificationPreference, NotificationEvent
from .services import CLAIM_LEASE


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(UnfoldModelAdmin):
    list_display = ['user', 'email_enabled', 'on_debt_change', 'on_status_change', 'on_executive_change']
    list_filter = ['email_enabled', 'on_debt_change', 'on_status_change']
    search_fields = ['user__email']


@admin.register(NotificationEvent)
class NotificationEventAdmin(UnfoldModelAdmin):
    list_display = ['title', 'event_type', 'company_name', 'user', 'status', 'attempts', 'created_at']
    list_filter = ['event_type', 'status', 'created_at']
    search_fields = ['title', 'company_ico', 'company_name', 'user__email']
    readonly_fields = ['created_at', 'status', 'attempts', 'last_error']
    ordering = ['-created_at']
    actions = ['reset_to_pending']

    @admin.action(description='Reset na pending (opätovné odoslanie zlyhaných)')
    def reset_to_pending(self, request, queryset):
        """Re-queue failed events and stale 'sending' (past the claim lease).

        Intentionally excludes 'sent' — resetting successfully delivered events
        would re-send duplicate emails to users.
        """
        stale_since = timezone.now() - CLAIM_LEASE
        to_reset = queryset.filter(
            Q(status=NotificationEvent.Status.FAILED)
            | Q(status=NotificationEvent.Status.SENDING, claimed_at__lt=stale_since)
        )
        updated = to_reset.update(
            status=NotificationEvent.Status.PENDING,
            attempts=0,
            last_error='',
            claimed_at=None,
        )
        self.message_user(request, f'{updated} udalostí bolo resetnutých na pending.')
