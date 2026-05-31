from django.contrib import admin

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
except ImportError:
    from django.contrib.admin import ModelAdmin as UnfoldModelAdmin

from .models import NotificationPreference, NotificationEvent


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(UnfoldModelAdmin):
    list_display = ['user', 'email_enabled', 'on_debt_change', 'on_status_change', 'on_executive_change']
    list_filter = ['email_enabled', 'on_debt_change', 'on_status_change']
    search_fields = ['user__email']


@admin.register(NotificationEvent)
class NotificationEventAdmin(UnfoldModelAdmin):
    list_display = ['title', 'event_type', 'company_name', 'user', 'sent_email', 'created_at']
    list_filter = ['event_type', 'sent_email', 'created_at']
    search_fields = ['title', 'company_ico', 'company_name', 'user__email']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
