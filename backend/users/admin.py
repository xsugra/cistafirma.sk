from django.contrib import admin
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

# Import Unfold pre moderný admin
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    from unfold.decorators import display as unfold_display
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    unfold_display = admin.display
    UNFOLD_AVAILABLE = False


@admin.register(User)
class CustomUserAdmin(UnfoldModelAdmin if UNFOLD_AVAILABLE else admin.ModelAdmin):
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

    readonly_fields = ('created_at', 'last_login')

    # Fieldsets pre vytvorenie nového používateľa
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'username',
                    'password1',
                    'password2'
                )
            }
        ),
        (
            'Personal info',
            {
                'classes': ('wide',),
                'fields': (
                    'first_name',
                    'last_name'
                )
            }
        ),
        (
            'Subscription',
            {
                'classes': ('wide',),
                'fields': ('subscription_plan',)
            }
        ),
        (
            'Permissions',
            {
                'classes': ('wide',),
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser'
                )
            }
        ),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        return self.fieldsets

    def get_form(self, request, obj=None, **kwargs):
        defaults = {"form": self.add_form if obj is None else self.form}
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)

    # Fieldsets pre editáciu existujúceho používateľa
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
        ),
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
