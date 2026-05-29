from django.contrib import admin

from .models import Person, PersonCompanyRelation

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    UNFOLD_AVAILABLE = False


class PersonCompanyRelationInline(admin.TabularInline):
    model = PersonCompanyRelation
    extra = 0
    readonly_fields = ("company", "role", "role_display", "vznik_funkcie", "zanik_funkcie", "is_active")
    fields = ("company", "role", "role_display", "vznik_funkcie", "is_active")


@admin.register(Person)
class PersonAdmin(UnfoldModelAdmin):
    list_display = ("name", "person_ico", "relations_count", "created_at")
    search_fields = ("name", "person_ico", "fingerprint")
    list_filter = ("is_legal_entity",)
    readonly_fields = ("fingerprint", "created_at", "updated_at")
    inlines = [PersonCompanyRelationInline]

    def relations_count(self, obj):
        return obj.company_relations.count()
    relations_count.short_description = "Počet firiem"


@admin.register(PersonCompanyRelation)
class PersonCompanyRelationAdmin(UnfoldModelAdmin):
    list_display = ("person", "company", "role", "is_active", "vznik_funkcie")
    list_filter = ("role", "is_active", "source")
    search_fields = ("person__name", "company__nazov_UJ", "company__ico")
    raw_id_fields = ("person", "company")
