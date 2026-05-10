from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

# Import Unfold pre moderný admin
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
    from unfold.decorators import display as unfold_display
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    unfold_display = admin.display
    UNFOLD_AVAILABLE = False


@admin.register(User)
class CustomUserAdmin(UserAdmin, UnfoldModelAdmin if UNFOLD_AVAILABLE else object):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    # Zobrazenie v zozname
    list_display = (
        'email',
        'username',
        'get_plan_name',
        'is_staff',
        'is_active'
    )

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'email',
                    'password'
                )
            }
        ),
        (
            'Personal info',
            {
                'fields': (
                    'first_name',
                    'last_name',
                    'username'
                )
            }
        ),
        (
            'Subscription',
            {
                'fields': ('subscription_plan',)
            }
        ),  # Tu admin priradí plán
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser'
                )
            }
        ),
        (
            'Important dates',
            {
                'fields': (
                    'last_login',
                    'created_at'
                )
            }
        ),
    )

    # Metóda na pekné zobrazenie mena plánu v zozname userov
    @unfold_display(description='Subscription Plan')
    def get_plan_name(self, obj):
        return obj.subscription_plan.name if obj.subscription_plan else "-"
