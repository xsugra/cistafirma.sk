from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
import csv
from io import BytesIO
from .models import Company, CompanyFinancialResult, LEGAL_FORMS_SHORT
from registers.models import OrsrCompanyProfile

# Import Unfold pre moderný admin
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    from unfold.decorators import action as unfold_action
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    unfold_action = admin.action
    UNFOLD_AVAILABLE = False


class LegalFormFilter(admin.SimpleListFilter):
    title = 'Právna forma'
    parameter_name = 'pravna_forma'

    def lookups(self, request, model_admin):
        # Bezpečne získame všetky unikátne právne formy pomocou Django ORM
        try:
            # Použijeme values_list s distinct pre unikátne hodnoty
            used_forms_queryset = Company.objects.exclude(
                pravna_forma__isnull=True
            ).exclude(
                pravna_forma__exact=''
            ).values_list('pravna_forma', flat=True).distinct().order_by('pravna_forma')
            
            # Konvertujeme na set pre istotu a potom zoradíme
            used_forms = sorted(set(used_forms_queryset))
            
            lookups = []
            for form_code in used_forms:
                # Konvertujeme na string a očistíme
                form_code_str = str(form_code).strip()
                if form_code_str:  # Preskočíme prázdne hodnoty
                    # Použijeme skratky pre filter
                    form_short = LEGAL_FORMS_SHORT.get(form_code_str, f'Neznáma ({form_code_str})')
                    lookups.append((form_code_str, f'{form_code_str} - {form_short}'))
            
            return lookups
            
        except Exception as e:
            # Ak sa niečo pokazí, vrátime aspoň základné formy
            return [
                ('112', '112 - s. r. o.'),
                ('121', '121 - a. s.'),
                ('101', '101 - FO-podnikateľ'),
                ('111', '111 - v. o. s.'),
            ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(pravna_forma=self.value())
        return queryset


class RokZalozeniaFilter(admin.SimpleListFilter):
    """Filter pre rok založenia firmy - umožňuje filtrovať firmy podľa roku vzniku."""
    title = 'Rok založenia'
    parameter_name = 'rok_zalozenia'

    def lookups(self, request, model_admin):
        try:
            # Získame všetky unikátne roky založenia z databázy
            # datum_zalozenia je DateField, extrahujeme rok
            years_queryset = Company.objects.exclude(
                datum_zalozenia__isnull=True
            ).dates('datum_zalozenia', 'year', order='DESC')
            
            lookups = []
            for date_obj in years_queryset:
                year = date_obj.year
                lookups.append((str(year), str(year)))
            
            return lookups
            
        except Exception:
            # Fallback - vrátime posledných 30 rokov
            import datetime
            current_year = datetime.date.today().year
            return [(str(y), str(y)) for y in range(current_year, current_year - 30, -1)]

    def queryset(self, request, queryset):
        if self.value():
            year = int(self.value())
            return queryset.filter(datum_zalozenia__year=year)
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
        ('ORSR základ', {
            'fields': (
                ('ico', 'oddiel', 'vlozka_cislo'),
                'obchodne_meno',
                'sidlo',
                ('den_zapisu', 'pravna_forma'),
            ),
        }),
        ('ORSR osoby a väzby', {
            'fields': ('statutarny_organ', 'prokura', 'spolocnici', 'vklady_spolocnikov'),
            'classes': ('collapse',),
        }),
        ('ORSR podnikanie a kapitál', {
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
class CompanyAdmin(UnfoldModelAdmin):
    """
    Profesionálne admin rozhranie pre správu firiem.
    Zahŕňa vyhľadávanie, filtrovanie, custom akcie pre RUZ sync a kontrolu dlhov.
    """
    
    # === LIST DISPLAY ===
    list_display = [
        'ico', 'nazov_UJ', 'mesto', 'legal_form_display', 
        'datum_zalozenia', 'datum_zrusenia_display',
        'vat_payer_display', 'tax_reliability_display',
        'debt_status_display', 'datum_poslednej_upravy',
    ]
    
    list_display_links = ['ico', 'nazov_UJ']
    inlines = [OrsrCompanyProfileInline, CompanyFinancialResultInline]
    change_form_template = 'admin/companies/company/change_form.html'

    # === SEARCH ===
    search_fields = [
        'ico', 'nazov_UJ', 'dic', 'ic_dph', 'mesto', 'ulica', 'ruz_id',
    ]
    search_help_text = "Vyhľadávanie podľa IČO, názvu, DIČ, IČ DPH, mesta, ulice alebo RUZ ID"
    
    # === FILTERING ===
    list_filter = [
        LegalFormFilter,  # Nahradíme obyčajný filter za custom filter
        RokZalozeniaFilter,  # Filter podľa roku založenia
        'kraj',
        'velkost_organizacie',
        'vat_payer',
        'tax_reliability',
        'konsolidovana',
        ('datum_zrusenia', admin.EmptyFieldListFilter),  # Aktívne/Zrušené firmy
        ('debt_vszp', admin.EmptyFieldListFilter),
        ('debt_soc_poist', admin.EmptyFieldListFilter),
        ('tax_debt', admin.EmptyFieldListFilter),
    ]
    
    # === ORDERING ===
    ordering = ['-datum_poslednej_upravy', 'nazov_UJ']
    
    # === PAGINATION ===
    list_per_page = 50
    list_max_show_all = 500
    
    # === READONLY FIELDS ===
    readonly_fields = [
        'ruz_id', 'datum_poslednej_upravy', 'last_insurance_debt', 'fs_update_date',
        'id_uctovnych_zavierok', 'id_vyrocnych_sprav',
    ]
    
    # === FIELDSETS ===
    fieldsets = (
        ('Základné údaje', {
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
        ('Klasifikácia', {
            'fields': (
                ('pravna_forma', 'sk_NACE'),
                ('velkost_organizacie', 'druh_vlastnictva'),
                'konsolidovana',
            )
        }),
        ('Dátumy', {
            'fields': (
                ('datum_zalozenia', 'datum_zrusenia'),
                'datum_poslednej_upravy',
            )
        }),
        ('DPH a Finančná správa', {
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
        ('Dlhy v poisťovniach', {
            'fields': (
                ('debt_vszp', 'debt_soc_poist'),
                'last_insurance_debt',
            ),
            'classes': ('collapse',),
        }),
        ('Účtovné závierky a Výročné správy', {
            'fields': (
                'id_uctovnych_zavierok',
                'id_vyrocnych_sprav',
            ),
            'classes': ('collapse',),
        }),
        ('Zdroj dát', {
            'fields': ('zdroj_dat',),
            'classes': ('collapse',),
        }),
    )
    
    # === CUSTOM DISPLAY METHODS ===
    @admin.display(description='Zrušená', boolean=True)
    def datum_zrusenia_display(self, obj):
        return obj.datum_zrusenia is not None
    
    @admin.display(description='Platiteľ DPH', boolean=True)
    def vat_payer_display(self, obj):
        return obj.vat_payer
    
    @admin.display(description='Právna forma')
    def legal_form_display(self, obj):
        if not obj.pravna_forma:
            return '-'
        form_short = LEGAL_FORMS_SHORT.get(str(obj.pravna_forma), 'Neznáma')
        return f"{obj.pravna_forma} - {form_short}"
    
    @admin.display(description='Daňová spoľahlivosť')
    def tax_reliability_display(self, obj):
        if not obj.tax_reliability:
            return '-'
        colors = {
            'vysoko spoľahlivý': 'green',
            'spoľahlivý': 'blue', 
            'nespoľahlivý': 'red',
        }
        color = colors.get(obj.tax_reliability.lower(), 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.tax_reliability
        )
    
    @admin.display(description='Stav dlhov')
    def debt_status_display(self, obj):
        debts = []
        if obj.debt_vszp and obj.debt_vszp > 0:
            debts.append(f'VŠZP: {obj.debt_vszp}€')
        if obj.debt_soc_poist and obj.debt_soc_poist > 0:
            debts.append(f'SP: {obj.debt_soc_poist}€')
        if obj.tax_debt and obj.tax_debt > 0:
            debts.append(f'Dane: {obj.tax_debt}€')
        
        if debts:
            return format_html(
                '<span style="color: red;">{}</span>',
                ', '.join(debts)
            )
        elif obj.last_insurance_debt:
            return mark_safe('<span style="color: green;">✓ OK</span>')
        return '-'
    
    # === ADMIN ACTIONS ===
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
    
    @admin.action(description='🔄 Synchronizovať z RUZ API')
    def sync_from_ruz(self, request, queryset):
        from registers.tasks import sync_single_company_from_ruz
        count = 0
        for company in queryset:
            sync_single_company_from_ruz.delay(company.ico)
            count += 1
        self.message_user(
            request, 
            f'Naplánovaná synchronizácia z RUZ pre {count} firiem.',
            messages.SUCCESS
        )

    @admin.action(description='🏛️ Synchronizovať údaje z ORSR')
    def sync_from_orsr(self, request, queryset):
        from registers.tasks import sync_company_orsr_data

        count = 0
        for company in queryset:
            sync_company_orsr_data.delay(company.id)
            count += 1
        self.message_user(
            request,
            f'Naplánovaná synchronizácia z ORSR pre {count} firiem.',
            messages.SUCCESS
        )

    @admin.action(description='📈 Synchronizovať hospodárske výsledky z RUZ')
    def sync_financials_from_ruz(self, request, queryset):
        from registers.tasks import sync_company_financials_from_ruz

        count = 0
        for company in queryset:
            sync_company_financials_from_ruz.delay(company.id)
            count += 1

        self.message_user(
            request,
            f'Naplánovaná synchronizácia hospodárskych výsledkov pre {count} firiem.',
            messages.SUCCESS,
        )

    @admin.action(description='🏥 Skontrolovať dlhy v poisťovniach')
    def check_insurance_debts(self, request, queryset):
        from registers.tasks import update_insurance_debt
        count = 0
        for company in queryset:
            update_insurance_debt.delay(company.id)
            count += 1
        self.message_user(
            request,
            f'Naplánovaná kontrola dlhov pre {count} firiem.',
            messages.SUCCESS
        )
    
    @admin.action(description='📊 Aktualizovať z Finančnej správy')
    def check_fs_data(self, request, queryset):
        # FS update funguje cez hromadný príkaz, tu len oznámime
        from registers.tasks import update_fs_data_task
        update_fs_data_task.delay()
        self.message_user(
            request,
            'Spustená aktualizácia z Finančnej správy pre všetky firmy.',
            messages.SUCCESS
        )
    
    @admin.action(description='🔄 Kompletný refresh všetkých dát')
    def refresh_all_data(self, request, queryset):
        from registers.tasks import (
            sync_single_company_from_ruz,
            sync_company_financials_from_ruz,
            sync_company_orsr_data,
            update_insurance_debt,
        )
        count = 0
        for company in queryset:
            sync_single_company_from_ruz.delay(company.ico)
            sync_company_orsr_data.delay(company.id)
            sync_company_financials_from_ruz.delay(company.id)
            update_insurance_debt.delay(company.id)
            count += 1
        self.message_user(
            request,
            f'Naplánovaný kompletný refresh pre {count} firiem.',
            messages.SUCCESS
        )
    
    # === EXPORT FIELDS DEFINITION ===
    EXPORT_FIELDS = [
        ('ico', 'IČO'),
        ('nazov_UJ', 'Názov'),
        ('dic', 'DIČ'),
        ('ic_dph', 'IČ DPH'),
        ('ulica', 'Ulica'),
        ('mesto', 'Mesto'),
        ('psc', 'PSČ'),
        ('okres', 'Okres'),
        ('kraj', 'Kraj'),
        ('pravna_forma', 'Právna forma'),
        ('sk_NACE', 'SK NACE'),
        ('velkost_organizacie', 'Veľkosť organizácie'),
        ('datum_zalozenia', 'Dátum založenia'),
        ('datum_zrusenia', 'Dátum zrušenia'),
        ('vat_payer', 'Platiteľ DPH'),
        ('tax_reliability', 'Daňová spoľahlivosť'),
        ('tax_debt', 'Daňový dlh'),
        ('debt_vszp', 'Dlh VŠZP'),
        ('debt_soc_poist', 'Dlh Sociálna poisťovňa'),
        ('datum_poslednej_upravy', 'Posledná aktualizácia'),
    ]
    
    def _get_export_data(self, queryset):
        """Helper to extract export data from queryset."""
        data = []
        for company in queryset:
            row = []
            for field_name, _ in self.EXPORT_FIELDS:
                value = getattr(company, field_name, '')
                if value is None:
                    value = ''
                elif isinstance(value, bool):
                    value = 'Áno' if value else 'Nie'
                row.append(value)
            data.append(row)
        return data
    
    def get_filtered_queryset(self, request):
        """Get the filtered queryset that matches the current admin changelist view."""
        # Start with all companies
        queryset = Company.objects.all()
        
        # Apply search filter
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
        
        # Apply list filters from GET parameters
        filter_mappings = {
            'pravna_forma__exact': 'pravna_forma',
            'kraj__exact': 'kraj',
            'velkost_organizacie__exact': 'velkost_organizacie',
            'vat_payer__exact': 'vat_payer',
            'tax_reliability__exact': 'tax_reliability',
            'konsolidovana__exact': 'konsolidovana',
            'pravna_forma': 'pravna_forma',  # pre jednoduché filtre
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
        
        # Handle EmptyFieldListFilter (isnull filters)
        isnull_mappings = {
            'datum_zrusenia__isempty': 'datum_zrusenia__isnull',
            'debt_vszp__isempty': 'debt_vszp__isnull',
            'debt_soc_poist__isempty': 'debt_soc_poist__isnull',
            'tax_debt__isempty': 'tax_debt__isnull',
        }
        
        for param, filter_field in isnull_mappings.items():
            value = request.GET.get(param)
            if value == '1':  # "Yes" = field is empty/null
                queryset = queryset.filter(**{filter_field: True})
            elif value == '0':  # "No" = field has value
                queryset = queryset.filter(**{filter_field: False})
        
        # Handle ordering
        ordering = request.GET.get('o')
        if ordering:
            try:
                # Convert admin ordering parameter to Django field names
                order_fields = []
                for field_idx in ordering.split('.'):
                    if field_idx.startswith('-'):
                        desc = True
                        field_idx = field_idx[1:]
                    else:
                        desc = False
                    
                    field_idx = int(field_idx)
                    if 0 <= field_idx < len(self.list_display):
                        field_name = self.list_display[field_idx]
                        if desc:
                            field_name = f'-{field_name}'
                        order_fields.append(field_name)
                
                if order_fields:
                    queryset = queryset.order_by(*order_fields)
            except (ValueError, IndexError):
                pass
        
        return queryset
    
    @admin.action(description='📥 Exportovať vybrané do CSV')
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="firmy_export.csv"'
        response.write('\ufeff')  # BOM for Excel UTF-8 support
        
        writer = csv.writer(response, delimiter=';')
        writer.writerow([label for _, label in self.EXPORT_FIELDS])
        
        for row in self._get_export_data(queryset):
            writer.writerow(row)
        
        self.message_user(request, f'Exportovaných {queryset.count()} firiem do CSV.', messages.SUCCESS)
        return response
    
    @admin.action(description='📥 Exportovať všetky filtrované do CSV')
    def export_filtered_to_csv(self, request, queryset):
        """Export all filtered results from changelist to CSV"""
        # Get the same filtered queryset that admin is currently displaying
        filtered_queryset = self.get_filtered_queryset(request)
        
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="firmy_filtrovane_export.csv"'
        response.write('\ufeff')  # BOM for Excel UTF-8 support
        
        writer = csv.writer(response, delimiter=';')
        writer.writerow([label for _, label in self.EXPORT_FIELDS])
        
        for row in self._get_export_data(filtered_queryset):
            writer.writerow(row)
        
        self.message_user(request, f'Exportovaných {filtered_queryset.count()} filtrovaných firiem do CSV.', messages.SUCCESS)
        return response
    
    @admin.action(description='📥 Exportovať vybrané do XLSX')
    def export_to_xlsx(self, request, queryset):
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            self.message_user(request, 'Chýba knižnica openpyxl. Nainštalujte: pip install openpyxl', messages.ERROR)
            return
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Firmy'
        
        # Header row with styling
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color='DAEEF3', end_color='DAEEF3', fill_type='solid')
        
        headers = [label for _, label in self.EXPORT_FIELDS]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
        
        # Data rows
        for row_idx, row_data in enumerate(self._get_export_data(queryset), 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=str(value) if value else '')
        
        # Auto-adjust column widths
        for col in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 50)
        
        # Create response
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="firmy_export.xlsx"'
        
        self.message_user(request, f'Exportovaných {queryset.count()} firiem do XLSX.', messages.SUCCESS)
        return response
    
    @admin.action(description='📥 Exportovať všetky filtrované do XLSX')
    def export_filtered_to_xlsx(self, request, queryset):
        """Export all filtered results from changelist to XLSX"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            self.message_user(request, 'Chýba knižnica openpyxl. Nainštalujte: pip install openpyxl', messages.ERROR)
            return
        
        # Get the same filtered queryset that admin is currently displaying
        filtered_queryset = self.get_filtered_queryset(request)
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Firmy'
        
        # Header row with styling
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color='DAEEF3', end_color='DAEEF3', fill_type='solid')
        
        headers = [label for _, label in self.EXPORT_FIELDS]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
        
        # Data rows
        for row_idx, row_data in enumerate(self._get_export_data(filtered_queryset), 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=str(value) if value else '')
        
        # Auto-adjust column widths
        for col in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 50)
        
        # Create response
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="firmy_filtrovane_export.xlsx"'
        
        self.message_user(request, f'Exportovaných {filtered_queryset.count()} filtrovaných firiem do XLSX.', messages.SUCCESS)
        return response
    
    # === CUSTOM ADMIN VIEWS ===
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
        """Spustí okamžitý full sync pre jednu firmu z detailu adminu."""
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
                f'✅ Full sync bol naplánovaný pre {company.nazov_UJ} ({company.ico}).',
                messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(
                request,
                f'❌ Nepodarilo sa spustiť sync: {str(exc)[:120]}',
                messages.ERROR,
            )

        return HttpResponseRedirect(reverse('admin:companies_company_change', args=[company.id]))
    
    def export_filtered_view(self, request):
        """Export all filtered companies to CSV or XLSX."""
        export_format = request.GET.get('format', 'csv')
        
        # Start with all companies
        queryset = Company.objects.all()
        
        # Apply search filter
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
        
        # Apply list filters from GET parameters
        filter_mappings = {
            'pravna_forma__exact': 'pravna_forma',
            'kraj__exact': 'kraj',
            'velkost_organizacie__exact': 'velkost_organizacie',
            'vat_payer__exact': 'vat_payer',
            'tax_reliability__exact': 'tax_reliability',
            'konsolidovana__exact': 'konsolidovana',
        }
        
        for param, field in filter_mappings.items():
            value = request.GET.get(param)
            if value:
                if value in ('True', 'true', '1'):
                    queryset = queryset.filter(**{field: True})
                elif value in ('False', 'false', '0'):
                    queryset = queryset.filter(**{field: False})
                else:
                    queryset = queryset.filter(**{field: value})
        
        # Handle EmptyFieldListFilter (isnull filters)
        isnull_mappings = {
            'datum_zrusenia__isempty': 'datum_zrusenia__isnull',
            'debt_vszp__isempty': 'debt_vszp__isnull',
            'debt_soc_poist__isempty': 'debt_soc_poist__isnull',
            'tax_debt__isempty': 'tax_debt__isnull',
        }
        
        for param, filter_field in isnull_mappings.items():
            value = request.GET.get(param)
            if value == '1':  # "Yes" = field is empty/null
                queryset = queryset.filter(**{filter_field: True})
            elif value == '0':  # "No" = field has value
                queryset = queryset.filter(**{filter_field: False})
        
        if export_format == 'xlsx':
            return self._export_queryset_xlsx(queryset)
        else:
            return self._export_queryset_csv(queryset)
    
    def _export_queryset_csv(self, queryset):
        """Generate CSV response from queryset."""
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="firmy_export.csv"'
        response.write('\ufeff')  # BOM for Excel UTF-8 support
        
        writer = csv.writer(response, delimiter=';')
        writer.writerow([label for _, label in self.EXPORT_FIELDS])
        
        for row in self._get_export_data(queryset):
            writer.writerow(row)
        
        return response
    
    def _export_queryset_xlsx(self, queryset):
        """Generate XLSX response from queryset."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            return HttpResponse('Chýba knižnica openpyxl.', status=500)
        
        wb = Workbook()
        ws = wb.active
        ws.title = 'Firmy'
        
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color='DAEEF3', end_color='DAEEF3', fill_type='solid')
        
        headers = [label for _, label in self.EXPORT_FIELDS]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
        
        for row_idx, row_data in enumerate(self._get_export_data(queryset), 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=str(value) if value else '')
        
        for col in ws.columns:
            max_length = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 50)
        
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="firmy_export.xlsx"'
        return response
    
    def add_company_from_ruz_view(self, request):
        """View pre pridanie novej firmy podľa IČO z RUZ."""
        from django.shortcuts import render, redirect
        from registers.integrations.ruz_api import RuzApi
        
        if request.method == 'POST':
            ico = request.POST.get('ico', '').strip()
            if not ico:
                self.message_user(request, 'IČO je povinné.', messages.ERROR)
                return redirect('admin:companies_company_changelist')
            
            # Skontroluj či firma už existuje
            if Company.objects.filter(ico=ico).exists():
                self.message_user(
                    request, 
                    f'Firma s IČO {ico} už existuje v databáze.',
                    messages.WARNING
                )
                return redirect('admin:companies_company_changelist')
            
            # Skúsime Celery task, ak nie je dostupný, spustíme synchrónne
            try:
                from registers.tasks import sync_single_company_from_ruz
                sync_single_company_from_ruz.delay(ico)
                self.message_user(
                    request,
                    f'Spustené vyhľadávanie a import firmy s IČO {ico} z RUZ (asynchrónne).',
                    messages.SUCCESS
                )
            except Exception as celery_error:
                # Celery/Redis nie je dostupný - spustíme synchrónne
                try:
                    from registers.tasks import sync_single_company_from_ruz
                    result = sync_single_company_from_ruz(ico)
                    self.message_user(
                        request,
                        f'Import dokončený: {result}',
                        messages.SUCCESS
                    )
                except Exception as e:
                    self.message_user(
                        request,
                        f'Chyba pri importe: {str(e)}',
                        messages.ERROR
                    )
            
            return redirect('admin:companies_company_changelist')
        
        # GET request - zobraz formulár
        context = {
            **self.admin_site.each_context(request),
            'title': 'Pridať firmu z RUZ API',
            'opts': self.model._meta,
        }
        return render(request, 'admin/companies/add_from_ruz.html', context)
    
    def trigger_full_ruz_sync_view(self, request):
        """View pre spustenie kompletnej synchronizácie z RUZ."""
        from django.shortcuts import redirect
        from registers.tasks import fetch_ruz_data_task
        
        if request.method == 'POST':
            try:
                fetch_ruz_data_task.delay()
                self.message_user(
                    request,
                    'Spustená kompletná synchronizácia z RUZ API. Toto môže trvať niekoľko hodín.',
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'Celery/Redis nie je dostupný. Spustite Redis: brew services start redis. Chyba: {str(e)[:100]}',
                    messages.ERROR
                )
        return redirect('admin:companies_company_changelist')
    
    def changelist_view(self, request, extra_context=None):
        """Pridáme extra tlačidlá a štatistiky do changelist view."""
        from registers.models import SyncProgress
        from django.db.models import Count, Q
        
        extra_context = extra_context or {}
        extra_context['show_ruz_buttons'] = True
        
        # Štatistiky pre dashboard
        total_companies = Company.objects.count()
        active_companies = Company.objects.filter(datum_zrusenia__isnull=True).count()
        companies_with_debts = Company.objects.filter(
            Q(debt_vszp__gt=0) | Q(debt_soc_poist__gt=0) | Q(tax_debt__gt=0)
        ).count()
        
        # Sync stav
        sync_progress = SyncProgress.objects.filter(sync_type='full').first()
        
        extra_context['dashboard_stats'] = {
            'total': total_companies,
            'active': active_companies,
            'inactive': total_companies - active_companies,
            'with_debts': companies_with_debts,
            'sync_progress': sync_progress,
        }
        
        return super().changelist_view(request, extra_context=extra_context)
