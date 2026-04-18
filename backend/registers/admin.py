from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse, path
from django.template.response import TemplateResponse
from .models import SyncProgress, SyncGapAnalysis, OrsrCompanyProfile

# Import Unfold pre moderný admin
try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    UNFOLD_AVAILABLE = False


@admin.register(SyncGapAnalysis)
class SyncGapAnalysisAdmin(UnfoldModelAdmin):
    """
    Admin rozhranie pre Gap Analysis - analýza a oprava dier v RUZ ID.
    """
    
    list_display = [
        'id', 'status_display', 'stats_display', 'progress_display',
        'created_at', 'actions_display'
    ]
    
    list_filter = ['status']
    
    readonly_fields = [
        'status', 'analyzed_min_id', 'analyzed_max_id', 
        'total_existing', 'total_missing', 'total_gaps',
        'gap_ranges_display', 'top_gaps_display',
        'repair_progress_id', 'repaired_count', 'skipped_count', 'error_count',
        'created_at', 'analyzed_at', 'completed_at', 'last_error',
    ]
    
    fieldsets = (
        ('Stav', {
            'fields': ('status',),
        }),
        ('Rozsah analýzy', {
            'fields': ('analyzed_min_id', 'analyzed_max_id', 'total_existing'),
        }),
        ('Výsledky analýzy', {
            'fields': ('total_missing', 'total_gaps', 'top_gaps_display'),
        }),
        ('Progress opravy', {
            'fields': ('repair_progress_id', 'repaired_count', 'skipped_count', 'error_count'),
        }),
        ('Časové záznamy', {
            'fields': ('created_at', 'analyzed_at', 'completed_at'),
        }),
        ('Chyby', {
            'fields': ('last_error',),
            'classes': ('collapse',),
        }),
    )
    
    ordering = ['-created_at']
    
    @admin.display(description='Stav')
    def status_display(self, obj):
        colors = {
            'pending': '#6b7280',
            'analyzing': '#3b82f6',
            'ready': '#10b981',
            'repairing': '#f59e0b',
            'completed': '#22c55e',
            'failed': '#ef4444',
        }
        icons = {
            'pending': '⏳',
            'analyzing': '🔍',
            'ready': '✅',
            'repairing': '🔧',
            'completed': '🎉',
            'failed': '❌',
        }
        color = colors.get(obj.status, '#6b7280')
        icon = icons.get(obj.status, '❓')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    
    @admin.display(description='Štatistiky')
    def stats_display(self, obj):
        return format_html(
            '<span title="Chýbajúcich / Dier">'
            '🕳️ {} ID v {} dierach</span>',
            f'{obj.total_missing:,}', obj.total_gaps
        )
    
    @admin.display(description='Progress opravy')
    def progress_display(self, obj):
        if obj.total_missing == 0:
            return '-'
        
        done = obj.repaired_count + obj.skipped_count
        percentage = round((done / obj.total_missing) * 100, 1) if obj.total_missing > 0 else 0
        color = '#22c55e' if percentage == 100 else '#3b82f6' if percentage > 0 else '#6b7280'
        
        return format_html(
            '<div style="width:120px; background:#e5e7eb; border-radius:4px; overflow:hidden;">'
            '<div style="width:{}%; background:{}; height:18px; text-align:center; color:white; font-size:11px; line-height:18px;">'
            '{}% ({:,})</div></div>',
            min(percentage, 100), color, percentage, done
        )
    
    @admin.display(description='Top diery')
    def top_gaps_display(self, obj):
        if not obj.gap_ranges:
            return 'Žiadne diery'
        
        # Zoradíme podľa veľkosti
        sorted_gaps = sorted(obj.gap_ranges, key=lambda x: x[1] - x[0], reverse=True)[:10]
        
        rows = []
        for i, gap in enumerate(sorted_gaps):
            start, end = gap
            size = end - start + 1
            rows.append(f'<tr><td>{i+1}.</td><td>{start:,} - {end:,}</td><td><strong>{size:,}</strong> ID</td></tr>')
        
        return format_html(
            '<table style="border-collapse:collapse; font-size:12px;">'
            '<tr style="background:#f3f4f6;"><th style="padding:4px 8px;">#</th>'
            '<th style="padding:4px 8px;">Rozsah</th><th style="padding:4px 8px;">Veľkosť</th></tr>'
            '{}</table>',
            mark_safe(''.join(rows))
        )
    
    @admin.display(description='Všetky diery (JSON)')
    def gap_ranges_display(self, obj):
        if not obj.gap_ranges:
            return '[]'
        return f'{len(obj.gap_ranges)} rozsahov (zobrazené v "Top diery")'
    
    @admin.display(description='Akcie')
    def actions_display(self, obj):
        buttons = []
        
        if obj.status == 'ready':
            buttons.append(
                f'<a href="{reverse("admin:registers_syncgapanalysis_repair", args=[obj.pk])}" '
                f'class="button" style="background:#10b981;color:white;padding:4px 8px;border-radius:4px;text-decoration:none;margin-right:4px;">'
                f'🔧 Opraviť diery</a>'
            )
        
        if obj.status == 'repairing':
            buttons.append(
                f'<a href="{reverse("admin:registers_syncgapanalysis_resume", args=[obj.pk])}" '
                f'class="button" style="background:#3b82f6;color:white;padding:4px 8px;border-radius:4px;text-decoration:none;margin-right:4px;">'
                f'▶️ Pokračovať</a>'
            )
        
        return mark_safe(' '.join(buttons)) if buttons else '-'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'trigger/analyze/',
                self.admin_site.admin_view(self.trigger_analyze_view),
                name='registers_syncgapanalysis_trigger_analyze',
            ),
            path(
                '<int:pk>/repair/',
                self.admin_site.admin_view(self.repair_view),
                name='registers_syncgapanalysis_repair',
            ),
            path(
                '<int:pk>/resume/',
                self.admin_site.admin_view(self.resume_view),
                name='registers_syncgapanalysis_resume',
            ),
        ]
        return custom_urls + urls
    
    def trigger_analyze_view(self, request):
        """Spustí novú analýzu dier"""
        from registers.tasks import analyze_ruz_gaps
        
        try:
            analyze_ruz_gaps.delay()
            messages.success(request, '🔍 Analýza dier bola naplánovaná. Sledujte progress v zozname.')
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
    
    def repair_view(self, request, pk):
        """Spustí opravu dier pre danú analýzu"""
        from registers.tasks import repair_ruz_gaps
        
        analysis = SyncGapAnalysis.objects.get(pk=pk)
        
        if analysis.status != 'ready':
            messages.error(request, 'Analýza nie je pripravená na opravu.')
            return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
        
        try:
            repair_ruz_gaps.delay(analysis_id=pk, workers=5)
            messages.success(
                request,
                f'🔧 Oprava {analysis.total_missing:,} chýbajúcich ID bola naplánovaná.'
            )
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
    
    def resume_view(self, request, pk):
        """Pokračuje v oprave"""
        from registers.tasks import repair_ruz_gaps
        
        analysis = SyncGapAnalysis.objects.get(pk=pk)
        
        try:
            repair_ruz_gaps.delay(analysis_id=pk, workers=5, resume=True)
            messages.success(
                request,
                f'▶️ Oprava pokračuje od ID {analysis.repair_progress_id:,}.'
            )
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['trigger_analyze_url'] = reverse('admin:registers_syncgapanalysis_trigger_analyze')
        
        from companies.models import Company
        from django.db.models import Min, Max
        
        # Základné štatistiky
        extra_context['total_companies'] = Company.objects.count()
        
        # DB stats pre rozsah
        stats = Company.objects.filter(ruz_id__isnull=False).aggregate(
            min_id=Min('ruz_id'),
            max_id=Max('ruz_id')
        )
        if stats['min_id']:
            stats['expected'] = stats['max_id'] - stats['min_id'] + 1
            extra_context['db_stats'] = stats
        
        # Posledná analýza
        latest = SyncGapAnalysis.objects.order_by('-created_at').first()
        if latest:
            extra_context['latest_analysis'] = latest
            if latest.gap_ranges:
                # Top 5 dier
                sorted_gaps = sorted(latest.gap_ranges, key=lambda x: x[1] - x[0], reverse=True)[:5]
                extra_context['top_gaps'] = [(g[0], g[1], g[1] - g[0] + 1) for g in sorted_gaps]
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SyncProgress)
class SyncProgressAdmin(UnfoldModelAdmin):
    """
    Admin rozhranie pre sledovanie a ovládanie RUZ synchronizácie.
    """

    change_list_template = 'admin/registers/syncprogress/change_list.html'

    list_display = [
        'sync_type_display', 'status_display', 'progress_display',
        'stats_display', 'rate_display', 'last_activity', 'actions_display'
    ]
    
    list_filter = ['sync_type', 'status']
    
    readonly_fields = [
        'sync_type', 'status', 'last_processed_ruz_id', 'zmenene_od',
        'total_processed', 'total_created', 'total_updated', 'total_skipped',
        'total_errors', 'started_at', 'last_activity', 'completed_at',
        'last_error', 'progress_bar', 'estimated_completion', 'sync_stats'
    ]
    
    fieldsets = (
        ('Stav synchronizácie', {
            'fields': ('sync_type', 'status', 'progress_bar', 'estimated_completion'),
        }),
        ('Pozícia', {
            'fields': ('last_processed_ruz_id', 'zmenene_od'),
        }),
        ('Štatistiky', {
            'fields': ('sync_stats', 'total_processed', 'total_created', 
                      'total_updated', 'total_skipped', 'total_errors'),
        }),
        ('Časové záznamy', {
            'fields': ('started_at', 'last_activity', 'completed_at'),
        }),
        ('Chyby a poznámky', {
            'fields': ('last_error', 'notes'),
            'classes': ('collapse',),
        }),
    )
    
    ordering = ['-last_activity']
    
    # === CUSTOM DISPLAY METHODS ===
    
    @admin.display(description='Typ')
    def sync_type_display(self, obj):
        icons = {'full': '🔄', 'incremental': '📥', 'repair': '🔧'}
        return f"{icons.get(obj.sync_type, '📊')} {obj.get_sync_type_display()}"
    
    @admin.display(description='Stav')
    def status_display(self, obj):
        colors = {
            'idle': '#6b7280',
            'running': '#10b981',
            'paused': '#f59e0b',
            'completed': '#3b82f6',
            'failed': '#ef4444',
        }
        icons = {
            'idle': '⏸️',
            'running': '▶️',
            'paused': '⏯️',
            'completed': '✅',
            'failed': '❌',
        }
        color = colors.get(obj.status, '#6b7280')
        icon = icons.get(obj.status, '❓')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    
    @admin.display(description='Progress')
    def progress_display(self, obj):
        percentage = obj.get_progress_percentage()
        color = '#10b981' if percentage > 50 else '#f59e0b' if percentage > 20 else '#6b7280'
        return format_html(
            '<div style="width:100px; background:#e5e7eb; border-radius:4px; overflow:hidden;">'
            '<div style="width:{}%; background:{}; height:20px; text-align:center; color:white; font-size:12px; line-height:20px;">'
            '{}%</div></div>',
            min(percentage, 100), color, percentage
        )
    
    @admin.display(description='Štatistiky')
    def stats_display(self, obj):
        return format_html(
            '<span title="Vytvorené / Aktualizované / Chyby">'
            '✨{} | 📝{} | ❌{}</span>',
            f"{obj.total_created:,}", f"{obj.total_updated:,}", obj.total_errors
        )
    
    @admin.display(description='Rýchlosť')
    def rate_display(self, obj):
        rate = obj.get_rate()
        if rate > 0:
            return f"{int(rate):,}/hod"
        return '-'
    
    @admin.display(description='Akcie')
    def actions_display(self, obj):
        buttons = []
        
        if obj.status in ['paused', 'failed']:
            buttons.append(
                f'<a href="{reverse("admin:registers_syncprogress_resume", args=[obj.pk])}" '
                f'class="button" style="background:#10b981;color:white;padding:4px 8px;border-radius:4px;text-decoration:none;margin-right:4px;">'
                f'▶️ Pokračovať</a>'
            )
        
        if obj.status == 'running':
            buttons.append(
                f'<a href="{reverse("admin:registers_syncprogress_pause", args=[obj.pk])}" '
                f'class="button" style="background:#f59e0b;color:white;padding:4px 8px;border-radius:4px;text-decoration:none;margin-right:4px;">'
                f'⏸️ Pozastaviť</a>'
            )
        
        return mark_safe(' '.join(buttons)) if buttons else '-'
    
    # === READONLY FIELD DISPLAYS ===
    
    @admin.display(description='Progress bar')
    def progress_bar(self, obj):
        percentage = obj.get_progress_percentage()
        return format_html(
            '<div style="width:300px; background:#e5e7eb; border-radius:8px; overflow:hidden; height:30px;">'
            '<div style="width:{}%; background: linear-gradient(90deg, #3b82f6, #10b981); height:30px; '
            'display:flex; align-items:center; justify-content:center; color:white; font-weight:bold;">'
            '{}% ({} firiem)</div></div>',
            min(percentage, 100), percentage, f"{obj.total_processed:,}"
        )
    
    @admin.display(description='Odhad dokončenia')
    def estimated_completion(self, obj):
        if obj.status != 'running':
            return '-'
        
        rate = obj.get_rate()
        if rate <= 0:
            return 'Počítam...'
        
        remaining = 2515481 - (obj.last_processed_ruz_id or 0)
        if remaining <= 0:
            return 'Takmer hotovo!'
        
        hours_remaining = remaining / max(rate, 1)
        if hours_remaining < 1:
            return f'~{int(hours_remaining * 60)} minút'
        elif hours_remaining < 24:
            return f'~{hours_remaining:.1f} hodín'
        else:
            days = hours_remaining / 24
            return f'~{days:.1f} dní'
    
    @admin.display(description='Súhrn štatistík')
    def sync_stats(self, obj):
        duration = obj.get_duration()
        duration_str = str(duration).split('.')[0] if duration else '-'
        
        return format_html(
            '<table style="border-collapse:collapse;">'
            '<tr><td style="padding:4px 12px 4px 0;"><strong>Trvanie:</strong></td><td>{}</td></tr>'
            '<tr><td style="padding:4px 12px 4px 0;"><strong>Rýchlosť:</strong></td><td>{} firiem/hod</td></tr>'
            '<tr><td style="padding:4px 12px 4px 0;"><strong>Posledné RUZ ID:</strong></td><td>{}</td></tr>'
            '</table>',
            duration_str, f"{int(obj.get_rate()):,}", f"{obj.last_processed_ruz_id or 0:,}"
        )
    
    # === CUSTOM URLS ===
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/resume/',
                self.admin_site.admin_view(self.resume_sync_view),
                name='registers_syncprogress_resume',
            ),
            path(
                '<int:pk>/pause/',
                self.admin_site.admin_view(self.pause_sync_view),
                name='registers_syncprogress_pause',
            ),
            path(
                'trigger/full/',
                self.admin_site.admin_view(self.trigger_full_sync_view),
                name='registers_syncprogress_trigger_full',
            ),
            path(
                'trigger/full-from-id/',
                self.admin_site.admin_view(self.trigger_full_sync_from_id_view),
                name='registers_syncprogress_trigger_full_from_id',
            ),
            path(
                'trigger/incremental/',
                self.admin_site.admin_view(self.trigger_incremental_sync_view),
                name='registers_syncprogress_trigger_incremental',
            ),
            path(
                'trigger/repair/',
                self.admin_site.admin_view(self.trigger_repair_sync_view),
                name='registers_syncprogress_trigger_repair',
            ),
            path(
                'trigger/gap-analysis/',
                self.admin_site.admin_view(self.trigger_gap_analysis_view),
                name='registers_syncprogress_trigger_gap_analysis',
            ),
        ]
        return custom_urls + urls
    
    def resume_sync_view(self, request, pk):
        """Pokračuje v pozastavenej synchronizácii cez Celery"""
        from registers.tasks import resume_full_ruz_sync, resume_repair_sync
        
        progress = SyncProgress.objects.get(pk=pk)
        
        if progress.status not in ['paused', 'failed']:
            messages.error(request, 'Synchronizáciu nie je možné obnoviť.')
            return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
        
        try:
            if progress.sync_type == 'repair':
                resume_repair_sync.delay()
            else:
                resume_full_ruz_sync.delay()
            
            messages.success(
                request, 
                f'✅ {progress.get_sync_type_display()} bola naplánovaná na pokračovanie od RUZ ID {progress.last_processed_ruz_id:,}.'
            )
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
    
    def pause_sync_view(self, request, pk):
        """Pozastaví bežiacu synchronizáciu"""
        progress = SyncProgress.objects.get(pk=pk)
        progress.pause('Pozastavené cez admin panel')
        messages.warning(request, '⏸️ Synchronizácia bola označená na pozastavenie.')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
    
    def trigger_full_sync_view(self, request):
        """Spustí Full Sync cez Celery"""
        from registers.tasks import start_full_ruz_sync
        
        try:
            start_full_ruz_sync.delay(reset=False)
            messages.success(request, '🔄 Full Sync bol naplánovaný. Sledujte progress v zozname.')
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
    
    def trigger_full_sync_from_id_view(self, request):
        """Spustí Full Sync od konkrétneho RUZ ID"""
        from registers.tasks import start_full_ruz_sync_from_id
        
        if request.method == 'POST':
            start_id = request.POST.get('start_id', '').strip()
            if start_id:
                try:
                    start_id = int(start_id)
                    start_full_ruz_sync_from_id.delay(start_id=start_id)
                    messages.success(request, f'🔄 Full Sync od RUZ ID {start_id:,} bol naplánovaný.')
                except ValueError:
                    messages.error(request, '❌ Neplatné RUZ ID.')
                except Exception as e:
                    messages.error(request, f'❌ Chyba: {str(e)[:100]}')
            else:
                messages.error(request, '❌ Zadajte RUZ ID.')
        
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
    
    def trigger_incremental_sync_view(self, request):
        """Spustí Incremental Sync cez Celery"""
        from registers.tasks import start_incremental_sync
        
        try:
            start_incremental_sync.delay()
            messages.success(request, '📥 Incremental Sync bol naplánovaný. Stiahne firmy zmenené od posledného syncu.')
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
    
    def trigger_repair_sync_view(self, request):
        """Spustí Repair Sync cez Celery"""
        from registers.tasks import start_repair_sync
        
        try:
            start_repair_sync.delay(workers=3)
            messages.success(request, '🔧 Repair Sync bol naplánovaný. Stiahne všetky chýbajúce firmy.')
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
    
    def trigger_gap_analysis_view(self, request):
        """Spustí Gap Analysis a presmeruje na Gap Analysis admin"""
        from registers.tasks import analyze_ruz_gaps
        
        try:
            analyze_ruz_gaps.delay()
            messages.success(request, '🔍 Analýza dier bola naplánovaná.')
        except Exception as e:
            messages.error(request, f'❌ Chyba: {str(e)[:100]}')
        
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
    
    # === CHANGE LIST CUSTOMIZATION ===
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # URL-y pre tlačidlá
        extra_context['trigger_full_url'] = reverse('admin:registers_syncprogress_trigger_full')
        extra_context['trigger_full_from_id_url'] = reverse('admin:registers_syncprogress_trigger_full_from_id')
        extra_context['trigger_incremental_url'] = reverse('admin:registers_syncprogress_trigger_incremental')
        extra_context['trigger_repair_url'] = reverse('admin:registers_syncprogress_trigger_repair')
        extra_context['trigger_gap_analysis_url'] = reverse('admin:registers_syncprogress_trigger_gap_analysis')
        extra_context['gap_analysis_url'] = reverse('admin:registers_syncgapanalysis_changelist')
        
        # Štatistiky
        from companies.models import Company, CompanyFinancialResult
        from django.db.models import Min, Max
        
        extra_context['total_companies'] = Company.objects.count()
        extra_context['total_orsr_profiles'] = OrsrCompanyProfile.objects.count()
        extra_context['companies_with_financials'] = CompanyFinancialResult.objects.values('company_id').distinct().count()
        extra_context['companies_without_orsr'] = max(extra_context['total_companies'] - extra_context['total_orsr_profiles'], 0)
        extra_context['companies_without_financials'] = max(extra_context['total_companies'] - extra_context['companies_with_financials'], 0)
        extra_context['running_syncs'] = SyncProgress.objects.filter(status='running').count()
        extra_context['failed_syncs'] = SyncProgress.objects.filter(status='failed').count()
        extra_context['completed_syncs'] = SyncProgress.objects.filter(status='completed').count()
        extra_context['recent_syncs'] = SyncProgress.objects.order_by('-last_activity')[:5]

        # DB stats
        stats = Company.objects.filter(ruz_id__isnull=False).aggregate(
            min_id=Min('ruz_id'),
            max_id=Max('ruz_id')
        )
        if stats['min_id']:
            stats['count'] = Company.objects.filter(ruz_id__isnull=False).count()
            stats['expected'] = stats['max_id'] - stats['min_id'] + 1
            stats['missing_estimate'] = stats['expected'] - stats['count']
            extra_context['db_stats'] = stats
        
        # Posledná gap analýza
        latest_gap = SyncGapAnalysis.objects.order_by('-created_at').first()
        if latest_gap:
            extra_context['latest_gap_analysis'] = latest_gap
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(OrsrCompanyProfile)
class OrsrCompanyProfileAdmin(UnfoldModelAdmin):
    list_display = [
        'ico', 'obchodne_meno', 'oddiel', 'vlozka_cislo',
        'fetch_ok', 'last_synced_at'
    ]
    search_fields = ['ico', 'obchodne_meno', 'company__nazov_UJ']
    list_filter = ['fetch_ok', 'oddiel']
    readonly_fields = ['last_synced_at', 'raw_sections', 'raw_payload']

