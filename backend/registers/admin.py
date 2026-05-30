from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse, path
from django.template.response import TemplateResponse
from .models import SyncProgress, SyncGapAnalysis, OrsrCompanyProfile, SyncFocusModeState
from .services import focus_mode as focus_mode_service

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    UNFOLD_AVAILABLE = False


@admin.register(SyncGapAnalysis)
class SyncGapAnalysisAdmin(UnfoldModelAdmin):
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
        ('Rozsah analyzy', {
            'fields': ('analyzed_min_id', 'analyzed_max_id', 'total_existing'),
        }),
        ('Vysledky analyzy', {
            'fields': ('total_missing', 'total_gaps', 'top_gaps_display'),
        }),
        ('Progress opravy', {
            'fields': ('repair_progress_id', 'repaired_count', 'skipped_count', 'error_count'),
        }),
        ('Casove zaznamy', {
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
        css = f'cf-badge cf-badge--{obj.status}'
        labels = {
            'pending': 'Caka',
            'analyzing': 'Analyzuje',
            'ready': 'Pripravene',
            'repairing': 'Opravuje',
            'completed': 'Dokoncene',
            'failed': 'Zlyhalo',
        }
        label = labels.get(obj.status, obj.status)
        return format_html(
            '<span class="{}">'
            '<span class="cf-badge__dot"></span>{}</span>',
            css, label
        )

    @admin.display(description='Statistiky')
    def stats_display(self, obj):
        return format_html(
            '<span style="font-variant-numeric:tabular-nums">'
            '<strong>{}</strong> chybajucich v <strong>{}</strong> dierach</span>',
            f'{obj.total_missing:,}', obj.total_gaps
        )

    @admin.display(description='Oprava')
    def progress_display(self, obj):
        if obj.total_missing == 0:
            return '-'
        done = obj.repaired_count + obj.skipped_count
        percentage = round((done / obj.total_missing) * 100, 1) if obj.total_missing > 0 else 0
        fill_class = 'cf-progress__fill--emerald' if percentage == 100 else 'cf-progress__fill--blue'
        return format_html(
            '<div class="cf-progress">'
            '<div class="cf-progress__fill {}" style="width:{}%">'
            '{}%</div></div>',
            fill_class, min(percentage, 100), percentage
        )

    @admin.display(description='Top diery')
    def top_gaps_display(self, obj):
        if not obj.gap_ranges:
            return 'Ziadne diery'
        sorted_gaps = sorted(obj.gap_ranges, key=lambda x: x[1] - x[0], reverse=True)[:10]
        rows = []
        for i, gap in enumerate(sorted_gaps):
            start, end = gap
            size = end - start + 1
            rows.append(
                f'<tr><td style="padding:6px 10px;color:var(--cf-slate-400)">{i+1}.</td>'
                f'<td style="padding:6px 10px;font-variant-numeric:tabular-nums">{start:,} &ndash; {end:,}</td>'
                f'<td style="padding:6px 10px;text-align:right;font-weight:700">{size:,} ID</td></tr>'
            )
        return format_html(
            '<table class="cf-table" style="max-width:400px">'
            '<thead><tr><th style="padding:6px 10px">#</th>'
            '<th style="padding:6px 10px">Rozsah</th>'
            '<th style="padding:6px 10px;text-align:right">Velkost</th></tr></thead>'
            '<tbody>{}</tbody></table>',
            mark_safe(''.join(rows))
        )

    @admin.display(description='Diery (JSON)')
    def gap_ranges_display(self, obj):
        if not obj.gap_ranges:
            return '[]'
        return f'{len(obj.gap_ranges)} rozsahov'

    @admin.display(description='Akcie')
    def actions_display(self, obj):
        buttons = []
        if obj.status == 'ready':
            url = reverse("admin:registers_syncgapanalysis_repair", args=[obj.pk])
            buttons.append(
                f'<a href="{url}" class="cf-btn cf-btn--success cf-btn--sm">Opravit</a>'
            )
        if obj.status == 'repairing':
            url = reverse("admin:registers_syncgapanalysis_resume", args=[obj.pk])
            buttons.append(
                f'<a href="{url}" class="cf-btn cf-btn--primary cf-btn--sm">Pokracovat</a>'
            )
        return mark_safe(' '.join(buttons)) if buttons else '-'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('trigger/analyze/', self.admin_site.admin_view(self.trigger_analyze_view),
                 name='registers_syncgapanalysis_trigger_analyze'),
            path('<int:pk>/repair/', self.admin_site.admin_view(self.repair_view),
                 name='registers_syncgapanalysis_repair'),
            path('<int:pk>/resume/', self.admin_site.admin_view(self.resume_view),
                 name='registers_syncgapanalysis_resume'),
        ]
        return custom_urls + urls

    def trigger_analyze_view(self, request):
        from registers.tasks import analyze_ruz_gaps
        try:
            analyze_ruz_gaps.delay()
            messages.success(request, 'Analyza dier bola naplanovana.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))

    def repair_view(self, request, pk):
        from registers.tasks import repair_ruz_gaps
        analysis = SyncGapAnalysis.objects.get(pk=pk)
        if analysis.status != 'ready':
            messages.error(request, 'Analyza nie je pripravena na opravu.')
            return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
        try:
            repair_ruz_gaps.delay(analysis_id=pk, workers=5)
            messages.success(request, f'Oprava {analysis.total_missing:,} chybajucich ID bola naplanovana.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))

    def resume_view(self, request, pk):
        from registers.tasks import repair_ruz_gaps
        analysis = SyncGapAnalysis.objects.get(pk=pk)
        try:
            repair_ruz_gaps.delay(analysis_id=pk, workers=5, resume=True)
            messages.success(request, f'Oprava pokracuje od ID {analysis.repair_progress_id:,}.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['trigger_analyze_url'] = reverse('admin:registers_syncgapanalysis_trigger_analyze')

        from companies.models import Company
        from django.db.models import Min, Max

        extra_context['total_companies'] = Company.objects.count()
        stats = Company.objects.filter(ruz_id__isnull=False).aggregate(
            min_id=Min('ruz_id'), max_id=Max('ruz_id')
        )
        if stats['min_id']:
            stats['expected'] = stats['max_id'] - stats['min_id'] + 1
            extra_context['db_stats'] = stats

        latest = SyncGapAnalysis.objects.order_by('-created_at').first()
        if latest:
            extra_context['latest_analysis'] = latest
            if latest.gap_ranges:
                sorted_gaps = sorted(latest.gap_ranges, key=lambda x: x[1] - x[0], reverse=True)[:5]
                extra_context['top_gaps'] = [(g[0], g[1], g[1] - g[0] + 1) for g in sorted_gaps]

        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SyncProgress)
class SyncProgressAdmin(UnfoldModelAdmin):
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
        ('Stav synchronizacie', {
            'fields': ('sync_type', 'status', 'progress_bar', 'estimated_completion'),
        }),
        ('Pozicia', {
            'fields': ('last_processed_ruz_id', 'zmenene_od'),
        }),
        ('Statistiky', {
            'fields': ('sync_stats', 'total_processed', 'total_created',
                       'total_updated', 'total_skipped', 'total_errors'),
        }),
        ('Casove zaznamy', {
            'fields': ('started_at', 'last_activity', 'completed_at'),
        }),
        ('Chyby a poznamky', {
            'fields': ('last_error', 'notes'),
            'classes': ('collapse',),
        }),
    )
    ordering = ['-last_activity']

    @admin.display(description='Typ')
    def sync_type_display(self, obj):
        type_labels = {
            'full': 'Full sync',
            'incremental': 'Inkrementalny',
            'repair': 'Opravny',
        }
        return type_labels.get(obj.sync_type, obj.sync_type)

    @admin.display(description='Stav')
    def status_display(self, obj):
        css = f'cf-badge cf-badge--{obj.status}'
        labels = {
            'idle': 'Neaktivny',
            'running': 'Beziaci',
            'paused': 'Pozastaveny',
            'completed': 'Dokonceny',
            'failed': 'Zlyhany',
        }
        label = labels.get(obj.status, obj.status)
        return format_html(
            '<span class="{}">'
            '<span class="cf-badge__dot"></span>{}</span>',
            css, label
        )

    @admin.display(description='Progress')
    def progress_display(self, obj):
        percentage = obj.get_progress_percentage()
        fill_class = 'cf-progress__fill--emerald' if percentage > 80 else 'cf-progress__fill--blue' if percentage > 20 else 'cf-progress__fill--amber'
        return format_html(
            '<div class="cf-progress">'
            '<div class="cf-progress__fill {}" style="width:{}%">'
            '{}%</div></div>',
            fill_class, min(percentage, 100), percentage
        )

    @admin.display(description='Statistiky')
    def stats_display(self, obj):
        return format_html(
            '<span style="font-size:12px;font-variant-numeric:tabular-nums">'
            '<span style="color:var(--cf-emerald-600)" title="Vytvorene">+{}</span>'
            ' <span style="color:var(--cf-blue-600)" title="Aktualizovane">~{}</span>'
            ' <span style="color:var(--cf-rose-500)" title="Chyby">{}</span></span>',
            f'{obj.total_created:,}', f'{obj.total_updated:,}',
            f'!{obj.total_errors}' if obj.total_errors else '-'
        )

    @admin.display(description='Rychlost')
    def rate_display(self, obj):
        rate = obj.get_rate()
        if rate > 0:
            return format_html(
                '<span style="font-variant-numeric:tabular-nums">{}/hod</span>',
                f'{int(rate):,}'
            )
        return '-'

    @admin.display(description='Akcie')
    def actions_display(self, obj):
        buttons = []
        if obj.status in ['paused', 'failed']:
            url = reverse("admin:registers_syncprogress_resume", args=[obj.pk])
            buttons.append(f'<a href="{url}" class="cf-btn cf-btn--success cf-btn--sm">Pokracovat</a>')
        if obj.status == 'running':
            url = reverse("admin:registers_syncprogress_pause", args=[obj.pk])
            buttons.append(f'<a href="{url}" class="cf-btn cf-btn--warning cf-btn--sm">Pozastavit</a>')
        return mark_safe(' '.join(buttons)) if buttons else '-'

    # ── Readonly field displays ──

    @admin.display(description='Progress bar')
    def progress_bar(self, obj):
        percentage = obj.get_progress_percentage()
        return format_html(
            '<div class="cf-progress" style="width:300px;height:28px">'
            '<div class="cf-progress__fill cf-progress__fill--blue" '
            'style="width:{}%;font-size:13px">'
            '{}% ({} firiem)</div></div>',
            min(percentage, 100), percentage, f'{obj.total_processed:,}'
        )

    @admin.display(description='Odhad dokoncenia')
    def estimated_completion(self, obj):
        if obj.status != 'running':
            return '-'
        rate = obj.get_rate()
        if rate <= 0:
            return 'Pocitam...'
        remaining = 2515481 - (obj.last_processed_ruz_id or 0)
        if remaining <= 0:
            return 'Takmer hotovo'
        hours_remaining = remaining / max(rate, 1)
        if hours_remaining < 1:
            return f'~{int(hours_remaining * 60)} min'
        if hours_remaining < 24:
            return f'~{hours_remaining:.1f} hod'
        return f'~{hours_remaining / 24:.1f} dni'

    @admin.display(description='Suhrn statistik')
    def sync_stats(self, obj):
        duration = obj.get_duration()
        duration_str = str(duration).split('.')[0] if duration else '-'
        return format_html(
            '<table class="cf-table" style="max-width:350px">'
            '<tr><td style="padding:6px 10px;font-weight:600">Trvanie</td><td style="padding:6px 10px">{}</td></tr>'
            '<tr><td style="padding:6px 10px;font-weight:600">Rychlost</td><td style="padding:6px 10px">{} firiem/hod</td></tr>'
            '<tr><td style="padding:6px 10px;font-weight:600">Posledne RUZ ID</td><td style="padding:6px 10px">{}</td></tr>'
            '</table>',
            duration_str, f'{int(obj.get_rate()):,}', f'{obj.last_processed_ruz_id or 0:,}'
        )

    # ── Custom URLs ──

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/resume/', self.admin_site.admin_view(self.resume_sync_view),
                 name='registers_syncprogress_resume'),
            path('<int:pk>/pause/', self.admin_site.admin_view(self.pause_sync_view),
                 name='registers_syncprogress_pause'),
            path('trigger/full/', self.admin_site.admin_view(self.trigger_full_sync_view),
                 name='registers_syncprogress_trigger_full'),
            path('trigger/full-from-id/', self.admin_site.admin_view(self.trigger_full_sync_from_id_view),
                 name='registers_syncprogress_trigger_full_from_id'),
            path('trigger/incremental/', self.admin_site.admin_view(self.trigger_incremental_sync_view),
                 name='registers_syncprogress_trigger_incremental'),
            path('trigger/repair/', self.admin_site.admin_view(self.trigger_repair_sync_view),
                 name='registers_syncprogress_trigger_repair'),
            path('trigger/gap-analysis/', self.admin_site.admin_view(self.trigger_gap_analysis_view),
                 name='registers_syncprogress_trigger_gap_analysis'),
        ]
        return custom_urls + urls

    def resume_sync_view(self, request, pk):
        from registers.tasks import resume_full_ruz_sync, resume_repair_sync
        progress = SyncProgress.objects.get(pk=pk)
        if progress.status not in ['paused', 'failed']:
            messages.error(request, 'Synchronizaciu nie je mozne obnovit.')
            return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
        try:
            if progress.sync_type == 'repair':
                resume_repair_sync.delay()
            else:
                resume_full_ruz_sync.delay()
            messages.success(
                request,
                f'{progress.get_sync_type_display()} pokracuje od RUZ ID {progress.last_processed_ruz_id:,}.'
            )
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

    def pause_sync_view(self, request, pk):
        progress = SyncProgress.objects.get(pk=pk)
        progress.pause('Pozastavene cez admin panel')
        messages.warning(request, 'Synchronizacia bola pozastavena.')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

    def trigger_full_sync_view(self, request):
        from registers.tasks import start_full_ruz_sync
        try:
            start_full_ruz_sync.delay(reset=False)
            messages.success(request, 'Full Sync bol naplanovany.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

    def trigger_full_sync_from_id_view(self, request):
        from registers.tasks import start_full_ruz_sync_from_id
        if request.method == 'POST':
            start_id = request.POST.get('start_id', '').strip()
            if start_id:
                try:
                    start_id = int(start_id)
                    start_full_ruz_sync_from_id.delay(start_id=start_id)
                    messages.success(request, f'Full Sync od RUZ ID {start_id:,} bol naplanovany.')
                except ValueError:
                    messages.error(request, 'Neplatne RUZ ID.')
                except Exception as e:
                    messages.error(request, f'Chyba: {str(e)[:100]}')
            else:
                messages.error(request, 'Zadajte RUZ ID.')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

    def trigger_incremental_sync_view(self, request):
        from registers.tasks import start_incremental_sync
        try:
            start_incremental_sync.delay()
            messages.success(request, 'Inkrementalny Sync bol naplanovany.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

    def trigger_repair_sync_view(self, request):
        from registers.tasks import start_repair_sync
        try:
            start_repair_sync.delay(workers=3)
            messages.success(request, 'Opravny Sync bol naplanovany.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

    def trigger_gap_analysis_view(self, request):
        from registers.tasks import analyze_ruz_gaps
        try:
            analyze_ruz_gaps.delay()
            messages.success(request, 'Analyza dier bola naplanovana.')
        except Exception as e:
            messages.error(request, f'Chyba: {str(e)[:100]}')
        return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['trigger_full_url'] = reverse('admin:registers_syncprogress_trigger_full')
        extra_context['trigger_full_from_id_url'] = reverse('admin:registers_syncprogress_trigger_full_from_id')
        extra_context['trigger_incremental_url'] = reverse('admin:registers_syncprogress_trigger_incremental')
        extra_context['trigger_repair_url'] = reverse('admin:registers_syncprogress_trigger_repair')
        extra_context['trigger_gap_analysis_url'] = reverse('admin:registers_syncprogress_trigger_gap_analysis')
        extra_context['gap_analysis_url'] = reverse('admin:registers_syncgapanalysis_changelist')

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

        stats = Company.objects.filter(ruz_id__isnull=False).aggregate(
            min_id=Min('ruz_id'), max_id=Max('ruz_id')
        )
        if stats['min_id']:
            stats['count'] = Company.objects.filter(ruz_id__isnull=False).count()
            stats['expected'] = stats['max_id'] - stats['min_id'] + 1
            stats['missing_estimate'] = stats['expected'] - stats['count']
            extra_context['db_stats'] = stats

        latest_gap = SyncGapAnalysis.objects.order_by('-created_at').first()
        if latest_gap:
            extra_context['latest_gap_analysis'] = latest_gap

        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SyncFocusModeState)
class SyncFocusModeStateAdmin(UnfoldModelAdmin):
    list_display = ['state_display', 'activated_at', 'activated_by', 'snapshot_size_display']
    readonly_fields = [
        'active', 'activated_at', 'deactivated_at', 'activated_by',
        'snapshot', 'last_revoked', 'snapshot_size_display',
    ]
    actions = ['action_enter_focus_mode', 'action_exit_focus_mode']

    def has_add_permission(self, request):
        return not SyncFocusModeState.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='Stav')
    def state_display(self, obj):
        if obj.active:
            return mark_safe(
                '<span class="cf-badge cf-badge--danger">'
                '<span class="cf-badge__dot"></span>Focus mode AKTIVNY</span>'
            )
        return mark_safe(
            '<span class="cf-badge cf-badge--idle">'
            '<span class="cf-badge__dot"></span>Neaktivny</span>'
        )

    @admin.display(description='Vypnute periodic tasky')
    def snapshot_size_display(self, obj):
        count = len(obj.snapshot or [])
        if count > 0:
            return format_html(
                '<span class="cf-badge cf-badge--warning">{} taskov</span>',
                count
            )
        return '0'

    @admin.action(description='Aktivovat focus mode')
    def action_enter_focus_mode(self, request, queryset):
        state = focus_mode_service.enter_focus_mode(request.user)
        messages.success(
            request,
            f'Focus mode aktivovany. Vypnutych {len(state.snapshot or [])} periodic taskov, '
            f'revokovanych {len(state.last_revoked or [])} beziacich taskov.'
        )

    @admin.action(description='Deaktivovat focus mode')
    def action_exit_focus_mode(self, request, queryset):
        focus_mode_service.exit_focus_mode(request.user)
        messages.success(request, 'Focus mode deaktivovany, periodic tasky obnovene.')


@admin.register(OrsrCompanyProfile)
class OrsrCompanyProfileAdmin(UnfoldModelAdmin):
    list_display = [
        'ico', 'obchodne_meno', 'oddiel', 'vlozka_cislo',
        'sync_status_display', 'last_synced_at'
    ]
    search_fields = ['ico', 'obchodne_meno', 'company__nazov_UJ']
    list_filter = ['fetch_ok', 'oddiel']
    readonly_fields = ['last_synced_at', 'raw_sections', 'raw_payload']

    @admin.display(description='Stav sync')
    def sync_status_display(self, obj):
        if obj.fetch_ok:
            return mark_safe(
                '<span class="cf-badge cf-badge--success">OK</span>'
            )
        if obj.fetch_ok is False:
            return mark_safe(
                '<span class="cf-badge cf-badge--danger">Chyba</span>'
            )
        return mark_safe(
            '<span class="cf-badge cf-badge--idle">Neoverene</span>'
        )
