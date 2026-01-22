from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(User)
class CustomUserAdmin(UserAdmin):
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
    @admin.display(description='Subscription Plan')
    def get_plan_name(self, obj):
        return obj.subscription_plan.name if obj.subscription_plan else "-"
