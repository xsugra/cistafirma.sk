from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
import csv
from .models import Company, CompanyFinancialResult, LEGAL_FORMS_SHORT
from registers.models import OrsrCompanyProfile
from core.admin_mixins import AdminDisplayMixin, XlsxExportMixin

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    from unfold.decorators import action as unfold_action, display as unfold_display
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    unfold_action = admin.action
    unfold_display = admin.display
    UNFOLD_AVAILABLE = False


class LegalFormFilter(admin.SimpleListFilter):
    title = 'Pravna forma'
    parameter_name = 'pravna_forma'

    def lookups(self, request, model_admin):
        try:
            used_forms_queryset = Company.objects.exclude(
                pravna_forma__isnull=True
            ).exclude(
                pravna_forma__exact=''
            ).values_list('pravna_forma', flat=True).distinct().order_by('pravna_forma')
            used_forms = sorted(set(used_forms_queryset))
            lookups = []
            for form_code in used_forms:
                form_code_str = str(form_code).strip()
                if form_code_str:
                    form_short = LEGAL_FORMS_SHORT.get(form_code_str, f'Neznama ({form_code_str})')
                    lookups.append((form_code_str, f'{form_code_str} - {form_short}'))
            return lookups
        except Exception:
            return [
                ('112', '112 - s. r. o.'),
                ('121', '121 - a. s.'),
                ('101', '101 - FO-podnikatel'),
                ('111', '111 - v. o. s.'),
            ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(pravna_forma=self.value())
        return queryset


class RokZalozeniaFilter(admin.SimpleListFilter):
    title = 'Rok zalozenia'
    parameter_name = 'rok_zalozenia'

    def lookups(self, request, model_admin):
        try:
            years_queryset = Company.objects.exclude(
                datum_zalozenia__isnull=True
            ).dates('datum_zalozenia', 'year', order='DESC')
            return [(str(d.year), str(d.year)) for d in years_queryset]
        except Exception:
            import datetime
            current_year = datetime.date.today().year
            return [(str(y), str(y)) for y in range(current_year, current_year - 30, -1)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(datum_zalozenia__year=int(self.value()))
        return queryset


class HasDebtFilter(admin.SimpleListFilter):
    title = 'Stav dlhov'
    parameter_name = 'has_debt'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'S dlhmi'),
            ('no', 'Bez dlhov'),
        ]

    def queryset(self, request, queryset):
        from django.db.models import Q
        if self.value() == 'yes':
            return queryset.filter(
                Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
            )
        if self.value() == 'no':
            return queryset.exclude(
                Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
            )
        return queryset


class DataCompletenessFilter(admin.SimpleListFilter):
    title = 'Kompletnost dat'
    parameter_name = 'data_completeness'

    def lookups(self, request, model_admin):
        return [
            ('has_orsr', 'S ORSR profilom'),
            ('no_orsr', 'Bez ORSR profilu'),
            ('has_financials', 'S financnymi vysledkami'),
            ('no_financials', 'Bez financnych vysledkov'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'has_orsr':
            return queryset.filter(orsr_profile__isnull=False)
        if self.value() == 'no_orsr':
            return queryset.filter(orsr_profile__isnull=True)
        if self.value() == 'has_financials':
            return queryset.filter(financial_results__isnull=False).distinct()
        if self.value() == 'no_financials':
            return queryset.filter(financial_results__isnull=True)
        return queryset


class OrsrCompanyProfileInline(admin.StackedInline):
    model = OrsrCompanyProfile
    can_delete = False
    extra = 0
    max_num = 1
    readonly_fields = [
        'ico', 'oddiel', 'vlozka_cislo', 'obchodne_meno', 'sidlo',
        'den_zapisu', 'pravna_forma', 'konanie_menom_spolocnosti',
        'vyska_zakladneho_imania', 'predmet_podnikania', 'spolocnici',
        'vklady_spolocnikov', 'statutarny_organ', 'prokura', 'orsr_aktualizacia_dat',
        'orsr_datum_vypisu', 'source_url', 'fetch_ok', 'last_error',
        'last_synced_at', 'raw_sections', 'raw_payload',
    ]
    fieldsets = (
        ('ORSR zaklad', {
            'fields': (
                ('ico', 'oddiel', 'vlozka_cislo'),
                'obchodne_meno',
                'sidlo',
                ('den_zapisu', 'pravna_forma'),
            ),
        }),
        ('ORSR osoby a vazby', {
            'fields': ('statutarny_organ', 'prokura', 'spolocnici', 'vklady_spolocnikov'),
            'classes': ('collapse',),
        }),
        ('ORSR podnikanie a kapital', {
            'fields': ('predmet_podnikania', 'konanie_menom_spolocnosti', 'vyska_zakladneho_imania'),
            'classes': ('collapse',),
        }),
        ('ORSR meta', {
            'fields': (
                ('orsr_aktualizacia_dat', 'orsr_datum_vypisu'),
                'source_url',
                ('fetch_ok', 'last_synced_at'),
                'last_error',
                'raw_sections',
                'raw_payload',
            ),
            'classes': ('collapse',),
        }),
    )


class CompanyFinancialResultInline(admin.TabularInline):
    model = CompanyFinancialResult
    extra = 0
    fields = ('year', 'revenue', 'profit', 'source', 'updated_at')
    readonly_fields = ('updated_at',)
    ordering = ('-year',)


@admin.register(Company)
class CompanyAdmin(AdminDisplayMixin, XlsxExportMixin, UnfoldModelAdmin):
    list_display = [
        'ico', 'nazov_UJ', 'mesto', 'legal_form_display',
        'datum_zalozenia', 'status_display',
        'vat_payer_display', 'tax_reliability_display',
        'risk_display', 'data_quality_display',
        'datum_poslednej_upravy',
    ]

    list_display_links = ['ico', 'nazov_UJ']
    inlines = [OrsrCompanyProfileInline, CompanyFinancialResultInline]
    change_form_template = 'admin/companies/company/change_form.html'

    search_fields = [
        'ico', 'nazov_UJ', 'dic', 'ic_dph', 'mesto', 'ulica', 'ruz_id',
    ]
    search_help_text = "Hladanie: ICO, nazov, DIC, IC DPH, mesto, ulica, RUZ ID"

    list_filter = [
        LegalFormFilter,
        RokZalozeniaFilter,
        HasDebtFilter,
        DataCompletenessFilter,
        'kraj',
        'velkost_organizacie',
        'vat_payer',
        'tax_reliability',
        'konsolidovana',
        ('datum_zrusenia', admin.EmptyFieldListFilter),
    ]

    ordering = ['-datum_poslednej_upravy', 'nazov_UJ']
    list_per_page = 50
    list_max_show_all = 500

    readonly_fields = [
        'ruz_id', 'datum_poslednej_upravy', 'last_insurance_debt', 'fs_update_date',
        'id_uctovnych_zavierok', 'id_vyrocnych_sprav',
    ]

    fieldsets = (
        ('Zakladne udaje', {
            'fields': (
                ('ico', 'dic', 'sid'),
                'nazov_UJ',
                'ruz_id',
            )
        }),
        ('Adresa', {
            'fields': (
                ('ulica', 'mesto'),
                ('psc', 'okres', 'kraj'),
                'sidlo',
            )
        }),
        ('Klasifikacia', {
            'fields': (
                ('pravna_forma', 'sk_NACE'),
                ('velkost_organizacie', 'druh_vlastnictva'),
                'konsolidovana',
            )
        }),
        ('Datumy', {
            'fields': (
                ('datum_zalozenia', 'datum_zrusenia'),
                'datum_poslednej_upravy',
            )
        }),
        ('DPH a Financna sprava', {
            'fields': (
                ('vat_payer', 'ic_dph'),
                ('datum_reg_dph', 'vat_deleted_date'),
                'vat_deleted_reason',
                'tax_reliability',
                'tax_debt',
                'bank_accounts',
                'fs_update_date',
            ),
            'classes': ('collapse',),
        }),
        ('Dlhy v poistovniach', {
            'fields': (
                ('debt_vszp', 'debt_soc_poist'),
                'last_insurance_debt',
            ),
            'classes': ('collapse',),
        }),
        ('Uctovne zavierky a Vyrocne spravy', {
            'fields': (
                'id_uctovnych_zavierok',
                'id_vyrocnych_sprav',
            ),
            'classes': ('collapse',),
        }),
        ('Zdroj dat', {
            'fields': ('zdroj_dat',),
            'classes': ('collapse',),
        }),
    )

    # ── Display Methods ──

    @unfold_display(description='Stav')
    def status_display(self, obj):
        if obj.datum_zrusenia:
            return self.badge('Zrusena', 'danger')
        return self.badge('Aktivna', 'success')

    @unfold_display(description='DPH', boolean=True)
    def vat_payer_display(self, obj):
        return obj.vat_payer

    @unfold_display(description='Pravna forma')
    def legal_form_display(self, obj):
        if not obj.pravna_forma:
            return '-'
        form_short = LEGAL_FORMS_SHORT.get(str(obj.pravna_forma), '?')
        return format_html(
            '<span title="{}">{}</span>',
            f'{obj.pravna_forma}', form_short
        )

    @unfold_display(description='Dan. spolahlivost')
    def tax_reliability_display(self, obj):
        if not obj.tax_reliability:
            return mark_safe('<span class="cf-risk cf-risk--unknown">-</span>')
        mapping = {
            'vysoko spoľahlivý': ('success', 'Vysoko'),
            'spoľahlivý': ('info', 'OK'),
            'nespoľahlivý': ('danger', 'Nespolahlivy'),
        }
        variant, label = mapping.get(obj.tax_reliability.lower(), ('idle', obj.tax_reliability))
        return self.badge(label, variant)

    @unfold_display(description='Riziko')
    def risk_display(self, obj):
        issues = []
        total_debt = 0
        if obj.debt_vszp and obj.debt_vszp > 0:
            issues.append(f'VSZP {obj.debt_vszp:,.0f}&euro;')
            total_debt += obj.debt_vszp
        if obj.debt_soc_poist and obj.debt_soc_poist > 0:
            issues.append(f'SP {obj.debt_soc_poist:,.0f}&euro;')
            total_debt += obj.debt_soc_poist
        if obj.tax_debt and obj.tax_debt > 0:
            issues.append(f'Dan {obj.tax_debt:,.0f}&euro;')
            total_debt += obj.tax_debt

        if issues:
            level = 'cf-badge--danger' if total_debt > 1000 else 'cf-badge--warning'
            return format_html(
                '<span class="{}" title="{}">'
                '<span class="cf-badge__dot"></span>{}</span>',
                f'cf-badge {level}',
                ', '.join(issues).replace('&euro;', '€'),
                f'{total_debt:,.0f}€'
            )
        if obj.last_insurance_debt:
            return mark_safe(
                '<span class="cf-badge cf-badge--success">OK</span>'
            )
        return mark_safe('<span class="cf-risk cf-risk--unknown">-</span>')

    @unfold_display(description='Data')
    def data_quality_display(self, obj):
        parts = []
        has_orsr = hasattr(obj, 'orsr_profile') and obj.orsr_profile is not None
        try:
            has_orsr = obj.orsr_profile is not None
        except OrsrCompanyProfile.DoesNotExist:
            has_orsr = False

        has_financials = obj.financial_results.exists() if hasattr(obj, 'financial_results') else False

        if has_orsr:
            parts.append('<span title="ORSR profil" style="color:var(--cf-emerald-500)">OR</span>')
        else:
            parts.append('<span title="Chyba ORSR" style="color:var(--cf-slate-300)">OR</span>')

        if has_financials:
            parts.append('<span title="Financne vysledky" style="color:var(--cf-emerald-500)">FIN</span>')
        else:
            parts.append('<span title="Chybaju financie" style="color:var(--cf-slate-300)">FIN</span>')

        if obj.vat_payer is not None:
            parts.append('<span title="DPH info" style="color:var(--cf-emerald-500)">DPH</span>')
        else:
            parts.append('<span title="Chyba DPH" style="color:var(--cf-slate-300)">DPH</span>')

        return format_html(
            '<span style="font-size:11px;font-weight:600;display:flex;gap:4px;">{}</span>',
            mark_safe(' '.join(parts))
        )

    # ── Actions ──

    actions = [
        'sync_from_ruz',
        'sync_from_orsr',
        'sync_financials_from_ruz',
        'check_insurance_debts',
        'check_fs_data',
        'refresh_all_data',
        'export_to_csv',
        'export_to_xlsx',
        'export_filtered_to_csv',
        'export_filtered_to_xlsx',
    ]

    @admin.action(description='Sync z RUZ API')
    def sync_from_ruz(self, request, queryset):
        from registers.tasks import sync_single_company_from_ruz
        count = 0
        for company in queryset:
            sync_single_company_from_ruz.delay(company.ico)
            count += 1
        self.message_user(request, f'Naplanovana synchronizacia z RUZ pre {count} firiem.', messages.SUCCESS)

    @admin.action(description='Sync z ORSR')
    def sync_from_orsr(self, request, queryset):
        from registers.tasks import sync_company_orsr_data
        count = 0
        for company in queryset:
            sync_company_orsr_data.delay(company.id)
            count += 1
        self.message_user(request, f'Naplanovana synchronizacia z ORSR pre {count} firiem.', messages.SUCCESS)

    @admin.action(description='Sync hosp. vysledky z RUZ')
    def sync_financials_from_ruz(self, request, queryset):
        from registers.tasks import sync_company_financials_from_ruz
        count = 0
        for company in queryset:
            sync_company_financials_from_ruz.delay(company.id)
            count += 1
        self.message_user(request, f'Naplanovana synchronizacia hosp. vysledkov pre {count} firiem.', messages.SUCCESS)

    @admin.action(description='Kontrola dlhov v poistovniach')
    def check_insurance_debts(self, request, queryset):
        from registers.tasks import update_insurance_debt
        count = 0
        for company in queryset:
            update_insurance_debt.delay(company.id)
            count += 1
        self.message_user(request, f'Naplanovana kontrola dlhov pre {count} firiem.', messages.SUCCESS)

    @admin.action(description='Aktualizovat z Financnej spravy')
    def check_fs_data(self, request, queryset):
        from registers.tasks import update_fs_data_task
        update_fs_data_task.delay()
        self.message_user(request, 'Spustena aktualizacia z Financnej spravy.', messages.SUCCESS)

    @admin.action(description='Kompletny refresh dat')
    def refresh_all_data(self, request, queryset):
        from registers.tasks import orchestrate_full_company_sync
        count = 0
        for company in queryset:
            orchestrate_full_company_sync.delay(company.id)
            count += 1
        self.message_user(request, f'Naplanovany kompletny refresh pre {count} firiem.', messages.SUCCESS)

    # ── Export Fields ──

    EXPORT_FIELDS = [
        ('ico', 'ICO'),
        ('nazov_UJ', 'Nazov'),
        ('dic', 'DIC'),
        ('ic_dph', 'IC DPH'),
        ('ulica', 'Ulica'),
        ('mesto', 'Mesto'),
        ('psc', 'PSC'),
        ('okres', 'Okres'),
        ('kraj', 'Kraj'),
        ('pravna_forma', 'Pravna forma'),
        ('sk_NACE', 'SK NACE'),
        ('velkost_organizacie', 'Velkost organizacie'),
        ('datum_zalozenia', 'Datum zalozenia'),
        ('datum_zrusenia', 'Datum zrusenia'),
        ('vat_payer', 'Platitel DPH'),
        ('tax_reliability', 'Danova spolahlivost'),
        ('tax_debt', 'Danovy dlh'),
        ('debt_vszp', 'Dlh VSZP'),
        ('debt_soc_poist', 'Dlh Socialna poistovna'),
        ('datum_poslednej_upravy', 'Posledna aktualizacia'),
    ]

    def get_filtered_queryset(self, request):
        queryset = Company.objects.all()
        search_query = request.GET.get('q', '')
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(ico__icontains=search_query) |
                Q(nazov_UJ__icontains=search_query) |
                Q(dic__icontains=search_query) |
                Q(ic_dph__icontains=search_query) |
                Q(mesto__icontains=search_query) |
                Q(ulica__icontains=search_query) |
                Q(ruz_id__icontains=search_query)
            )
        filter_mappings = {
            'pravna_forma__exact': 'pravna_forma',
            'kraj__exact': 'kraj',
            'velkost_organizacie__exact': 'velkost_organizacie',
            'vat_payer__exact': 'vat_payer',
            'tax_reliability__exact': 'tax_reliability',
            'konsolidovana__exact': 'konsolidovana',
            'pravna_forma': 'pravna_forma',
            'kraj': 'kraj',
            'velkost_organizacie': 'velkost_organizacie',
            'vat_payer': 'vat_payer',
            'tax_reliability': 'tax_reliability',
            'konsolidovana': 'konsolidovana',
        }
        for param, field in filter_mappings.items():
            value = request.GET.get(param)
            if value and value != 'all':
                if value in ('True', 'true', '1'):
                    queryset = queryset.filter(**{field: True})
                elif value in ('False', 'false', '0'):
                    queryset = queryset.filter(**{field: False})
                else:
                    queryset = queryset.filter(**{field: value})
        isnull_mappings = {
            'datum_zrusenia__isempty': 'datum_zrusenia__isnull',
            'debt_vszp__isempty': 'debt_vszp__isnull',
            'debt_soc_poist__isempty': 'debt_soc_poist__isnull',
            'tax_debt__isempty': 'tax_debt__isnull',
        }
        for param, filter_field in isnull_mappings.items():
            value = request.GET.get(param)
            if value == '1':
                queryset = queryset.filter(**{filter_field: True})
            elif value == '0':
                queryset = queryset.filter(**{filter_field: False})
        return queryset

    @admin.action(description='Export vybranych do CSV')
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="firmy_export.csv"'
        response.write('﻿')
        writer = csv.writer(response, delimiter=';')
        writer.writerow([label for _, label in self.EXPORT_FIELDS])
        for row in self._get_export_data(queryset):
            writer.writerow(row)
        self.message_user(request, f'Exportovanych {queryset.count()} firiem do CSV.', messages.SUCCESS)
        return response

    @admin.action(description='Export vsetkych filtrovanych do CSV')
    def export_filtered_to_csv(self, request, queryset):
        filtered_queryset = self.get_filtered_queryset(request)
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="firmy_filtrovane_export.csv"'
        response.write('﻿')
        writer = csv.writer(response, delimiter=';')
        writer.writerow([label for _, label in self.EXPORT_FIELDS])
        for row in self._get_export_data(filtered_queryset):
            writer.writerow(row)
        self.message_user(request, f'Exportovanych {filtered_queryset.count()} filtrovanych firiem do CSV.', messages.SUCCESS)
        return response

    @admin.action(description='Export vybranych do XLSX')
    def export_to_xlsx(self, request, queryset):
        response = self._build_xlsx_response(queryset, "firmy_export.xlsx")
        self.message_user(request, f'Exportovanych {queryset.count()} firiem do XLSX.', messages.SUCCESS)
        return response

    @admin.action(description='Export vsetkych filtrovanych do XLSX')
    def export_filtered_to_xlsx(self, request, queryset):
        filtered_queryset = self.get_filtered_queryset(request)
        response = self._build_xlsx_response(filtered_queryset, "firmy_filtrovane_export.xlsx")
        self.message_user(request, f'Exportovanych {filtered_queryset.count()} filtrovanych firiem do XLSX.', messages.SUCCESS)
        return response

    # ── Custom Admin Views ──

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:company_id>/sync-now/',
                self.admin_site.admin_view(self.sync_now_view),
                name='companies_company_sync_now',
            ),
            path(
                'add-from-ruz/',
                self.admin_site.admin_view(self.add_company_from_ruz_view),
                name='companies_company_add_from_ruz',
            ),
            path(
                'trigger-full-ruz-sync/',
                self.admin_site.admin_view(self.trigger_full_ruz_sync_view),
                name='companies_company_trigger_full_ruz_sync',
            ),
            path(
                'export-filtered/',
                self.admin_site.admin_view(self.export_filtered_view),
                name='companies_company_export_filtered',
            ),
        ]
        return custom_urls + urls

    def sync_now_view(self, request, company_id: int):
        from registers.tasks import sync_company_now
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            self.message_user(request, 'Firma neexistuje.', messages.ERROR)
            return HttpResponseRedirect(reverse('admin:companies_company_changelist'))
        try:
            sync_company_now.delay(company.id)
            self.message_user(
                request,
                f'Full sync naplanovany pre {company.nazov_UJ} ({company.ico}).',
                messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(
                request,
                f'Nepodarilo sa spustit sync: {str(exc)[:120]}',
                messages.ERROR,
            )
        return HttpResponseRedirect(reverse('admin:companies_company_change', args=[company.id]))

    def export_filtered_view(self, request):
        export_format = request.GET.get('format', 'csv')
        queryset = self.get_filtered_queryset(request)
        if export_format == 'xlsx':
            return self._export_queryset_xlsx(queryset)
        return self._export_queryset_csv(queryset)

    def _export_queryset_csv(self, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="firmy_export.csv"'
        response.write('﻿')
        writer = csv.writer(response, delimiter=';')
        writer.writerow([label for _, label in self.EXPORT_FIELDS])
        for row in self._get_export_data(queryset):
            writer.writerow(row)
        return response

    def _export_queryset_xlsx(self, queryset):
        return self._build_xlsx_response(queryset, "firmy_export.xlsx")

    def add_company_from_ruz_view(self, request):
        from django.shortcuts import render, redirect
        if request.method == 'POST':
            ico = request.POST.get('ico', '').strip()
            if not ico:
                self.message_user(request, 'ICO je povinne.', messages.ERROR)
                return redirect('admin:companies_company_changelist')
            if Company.objects.filter(ico=ico).exists():
                self.message_user(request, f'Firma s ICO {ico} uz existuje v databaze.', messages.WARNING)
                return redirect('admin:companies_company_changelist')
            try:
                from registers.tasks import sync_single_company_from_ruz
                sync_single_company_from_ruz.delay(ico)
                self.message_user(request, f'Import firmy s ICO {ico} z RUZ bol naplanovany.', messages.SUCCESS)
            except Exception as celery_error:
                try:
                    from registers.tasks import sync_single_company_from_ruz
                    result = sync_single_company_from_ruz(ico)
                    self.message_user(request, f'Import dokonceny: {result}', messages.SUCCESS)
                except Exception as e:
                    self.message_user(request, f'Chyba pri importe: {str(e)}', messages.ERROR)
            return redirect('admin:companies_company_changelist')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Pridat firmu z RUZ API',
            'opts': self.model._meta,
        }
        return render(request, 'admin/companies/add_from_ruz.html', context)

    def trigger_full_ruz_sync_view(self, request):
        from django.shortcuts import redirect
        from registers.tasks import fetch_ruz_data_task
        if request.method == 'POST':
            try:
                fetch_ruz_data_task.delay()
                self.message_user(
                    request,
                    'Kompletna synchronizacia z RUZ API bola spustena.',
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'Celery/Redis nie je dostupny. Chyba: {str(e)[:100]}',
                    messages.ERROR
                )
        return redirect('admin:companies_company_changelist')

    def changelist_view(self, request, extra_context=None):
        from registers.models import SyncProgress
        from django.db.models import Count, Q

        extra_context = extra_context or {}
        extra_context['show_ruz_buttons'] = True

        total_companies = Company.objects.count()
        active_companies = Company.objects.filter(datum_zrusenia__isnull=True).count()
        companies_with_debts = Company.objects.filter(
            Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
        ).count()
        companies_with_orsr = OrsrCompanyProfile.objects.count()
        companies_with_financials = CompanyFinancialResult.objects.values('company_id').distinct().count()

        sync_progress = SyncProgress.objects.filter(sync_type='full').first()

        extra_context['dashboard_stats'] = {
            'total': total_companies,
            'active': active_companies,
            'inactive': total_companies - active_companies,
            'with_debts': companies_with_debts,
            'with_orsr': companies_with_orsr,
            'without_orsr': max(total_companies - companies_with_orsr, 0),
            'with_financials': companies_with_financials,
            'without_financials': max(total_companies - companies_with_financials, 0),
            'sync_progress': sync_progress,
            'orsr_pct': round(companies_with_orsr / total_companies * 100, 1) if total_companies else 0,
            'fin_pct': round(companies_with_financials / total_companies * 100, 1) if total_companies else 0,
        }

        return super().changelist_view(request, extra_context=extra_context)
