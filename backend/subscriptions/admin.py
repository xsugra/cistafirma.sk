from django.contrib import admin
from .models import SubscriptionPlan

# Import Unfold pre moderný admin
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    UNFOLD_AVAILABLE = False


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(UnfoldModelAdmin):
    list_display = ('name', 'slug', 'price_eur', 'max_watched_companies', 'pdf_reports_per_month')
    list_filter = ('slug',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
