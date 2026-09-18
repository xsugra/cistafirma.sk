from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse, path
from django.template.response import TemplateResponse
from django.db.models import Count, Q
from datetime import datetime, timedelta
import json
from .models import SyncProgress, SyncGapAnalysis, OrsrCompanyProfile, SyncFocusModeState, IndividualEntity
from .services import focus_mode as focus_mode_service

try:
    from unfold.admin import ModelAdmin as UnfoldModelAdmin
    UNFOLD_AVAILABLE = True
except ImportError:
    UnfoldModelAdmin = admin.ModelAdmin
    UNFOLD_AVAILABLE = False


# Custom simple list filter to expose entity-type (companies / individuals / mixed)
class SyncEntityTypeFilter(admin.SimpleListFilter):
    title = 'Entity type'
    parameter_name = 'entity_type'

    def lookups(self, request, model_admin):
        return (
            ('companies', 'Právnické osoby (LPO)'),
            ('individuals', 'Fyzické osoby (SZCO)'),
            ('mixed', 'Zmiešané'),
        )

    def queryset(self, request, queryset):
        val = self.value()
        if not val:
            return queryset
        if val == 'companies':
            return queryset.filter(sync_type__icontains='companies')
        if val == 'individuals':
            return queryset.filter(sync_type__icontains='individuals')
        if val == 'mixed':
            # mixed refers to legacy 'full'/'incremental' types that cover both
            return queryset.filter(sync_type__in=['full', 'incremental', 'repair'])
        return queryset


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
        # A gap repair now claims the global RUZ slot, so while the walk is
        # running this dispatch does nothing at all. Saying "bola naplanovana"
        # then is the same false report `resume_sync_view` was fixed for.
        if _live_ruz_job() is not None:
            messages.warning(
                request,
                'RUZ bezi. Oprava dier by teraz neurobila nic; skus to, ked dobehne.'
            )
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
        if _live_ruz_job() is not None:
            messages.warning(
                request,
                'RUZ bezi. Oprava dier by teraz neurobila nic; skus to, ked dobehne.'
            )
            return HttpResponseRedirect(reverse('admin:registers_syncgapanalysis_changelist'))
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


def _live_ruz_job():
    """The RUZ job currently holding the global slot, or `None`.

    Every RUZ command claims this one row before it may write company data, so
    a dispatch that meets a live job returns without doing anything. Any view
    that reports "bolo zaradene" -- or offers a button that does -- has to ask
    this first, or it is reporting a resume that was never going to run.

    One definition rather than a copy per view: the three views that queue a
    repair and the two that offer a resume all have to agree on what "the slot
    is taken" means, and a check that drifts between them is a lie in whichever
    copy drifted.
    """
    from registers.models import SyncJob
    from registers.services.sync_engine import RUZ_CONCURRENCY_KEY

    return (
        SyncJob.objects
        .filter(concurrency_key=RUZ_CONCURRENCY_KEY, status__in=['queued', 'running'])
        .order_by('-queued_at')
        .first()
    )


@admin.register(SyncProgress)
class SyncProgressAdmin(UnfoldModelAdmin):
    change_list_template = 'admin/registers/syncprogress/change_list.html'

    #: The sync types the "Pokracovat" button can really continue. Everything
    #: else -- `full_companies`, `full_individuals`, `incremental_companies`,
    #: `incremental_individuals`, `repair_companies`, `repair_individuals` --
    #: has no resume path yet, and offering the button for them is how the page
    #: came to promise a resume it could not perform: the dispatch fell through
    #: to `resume_full_ruz_sync`, which looks for a `full` row, so a click on an
    #: `incremental` row restarted a different walk and then reported the
    #: incremental row's own cursor as though it had been continued.
    #:
    #: `incremental` resumes by re-running its own trigger: `start_incremental_sync`
    #: calls `fetch_ruz_data` without `--full-resync`, which finds the
    #: `incremental` row and continues from its stored cursor.
    RESUMABLE_SYNC_TYPES = ('full', 'repair', 'incremental')

    list_display = [
        'sync_type_display', 'entity_badge', 'status_display', 'progress_display',
        'stats_display', 'rate_display', 'last_activity', 'actions_display'
    ]
    list_filter = [
        'sync_type', 'status',
        SyncEntityTypeFilter,
    ]
    readonly_fields = [
        'sync_type', 'status', 'last_processed_ruz_id', 'zmenene_od',
        'total_processed', 'total_created', 'total_updated', 'total_skipped',
        'total_errors', 'started_at', 'last_activity', 'completed_at',
        'last_error', 'progress_bar', 'estimated_completion', 'sync_stats',
        'entity_type_info', 'detailed_summary'
    ]
    fieldsets = (
        ('Stav synchronizácie', {
            'fields': ('sync_type', 'status', 'progress_bar', 'estimated_completion', 'entity_type_info'),
        }),
        ('Pozícia v spracovaní', {
            'fields': ('last_processed_ruz_id', 'zmenene_od'),
        }),
        ('Detailné štatistiky', {
            'fields': ('detailed_summary', 'sync_stats', 'total_processed', 'total_created',
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
        # The type gate is not decoration: for a type with no resume path the
        # view now refuses, so offering the button would only produce a refusal
        # on the next page. Kept in step with `RESUMABLE_SYNC_TYPES`.
        #
        # A `running` row is offered only when nothing holds the RUZ slot. With
        # a live job the same row is a run in progress, and a "Pokracovat"
        # button on the walk that is currently working is an offer to restart
        # it. Without one it is the wreck a SIGKILL or a mid-run deploy leaves
        # -- the one case a resume exists for, and the one the status filter
        # alone cannot tell apart from a healthy run. The query runs only for
        # `running` rows, so the changelist does not pay for it per row.
        resumable = obj.status in ['paused', 'failed'] or (
            obj.status == 'running' and _live_ruz_job() is None
        )
        if resumable and obj.sync_type in self.RESUMABLE_SYNC_TYPES:
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

    @admin.display(description='Entita')
    def entity_badge(self, obj):
        """Show entity type badge"""
        if 'companies' in obj.sync_type:
            return format_html(
                '<span class="cf-badge cf-badge--info">'
                '<span class="cf-badge__dot"></span>LPO</span>'
            )
        elif 'individuals' in obj.sync_type:
            return format_html(
                '<span class="cf-badge cf-badge--warning">'
                '<span class="cf-badge__dot"></span>SZCO</span>'
            )
        else:
            return format_html(
                '<span class="cf-badge cf-badge--secondary">'
                '<span class="cf-badge__dot"></span>Zmiešané</span>'
            )

    @admin.display(description='Typ entity')
    def entity_type_info(self, obj):
        """Show which entity type is being synced"""
        if 'companies' in obj.sync_type:
            entity_type = 'Iba Právnické osoby (LPO) - firmy, s.r.o., a.s., atď.'
            icon = '🏢'
        elif 'individuals' in obj.sync_type:
            entity_type = 'Iba Fyzické osoby (SZCO) - podnikatelia, samostatne osobe'
            icon = '👤'
        else:
            entity_type = 'Zmiešané (LPO + SZCO) - obidva typy do svojich tabuliek'
            icon = '🔄'

        return format_html(
            '<div style="padding:12px;background:var(--cf-slate-50);border-radius:4px;'
            'border-left:4px solid var(--cf-blue-500);font-size:14px">'
            '<strong>{} Typ entít:</strong> {}</div>',
            icon, entity_type
        )

    @admin.display(description='Detaily')
    def detailed_summary(self, obj):
        """Show detailed statistics summary"""
        duration = obj.get_duration()
        duration_str = str(duration).split('.')[0] if duration else '-'

        return format_html(
            '<table style="font-size:13px;width:100%">'
            '<tr style="border-bottom:1px solid var(--cf-slate-200)">'
            '<td style="padding:8px;font-weight:600;width:30%">Spracovaných</td>'
            '<td style="padding:8px;text-align:right;font-weight:600">{:,}</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid var(--cf-slate-200)">'
            '<td style="padding:8px">Vytvorených</td>'
            '<td style="padding:8px;text-align:right;color:var(--cf-emerald-600)">+{:,}</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid var(--cf-slate-200)">'
            '<td style="padding:8px">Aktualizovaných</td>'
            '<td style="padding:8px;text-align:right;color:var(--cf-blue-600)">~{:,}</td>'
            '</tr>'
            '<tr style="border-bottom:1px solid var(--cf-slate-200)">'
            '<td style="padding:8px">Preskočených</td>'
            '<td style="padding:8px;text-align:right">⊘ {:,}</td>'
            '</tr>'
            '<tr style="border-bottom:2px solid var(--cf-slate-300)">'
            '<td style="padding:8px;color:var(--cf-rose-600);font-weight:600">Chýb</td>'
            '<td style="padding:8px;text-align:right;color:var(--cf-rose-600);font-weight:600">✗ {:,}</td>'
            '</tr>'
            '<tr>'
            '<td style="padding:8px;font-weight:600">Trvanie</td>'
            '<td style="padding:8px;text-align:right;font-weight:600">{}</td>'
            '</tr>'
            '</table>',
            obj.total_processed,
            obj.total_created,
            obj.total_updated,
            obj.total_skipped,
            obj.total_errors,
            duration_str
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
        """Queue a resume of *this* row, and only report what was queued.

        Two things this has to get right, and neither is visible from the page.

        The dispatch carries `progress.pk`. Without it the task picked the
        newest row of its own type, so clicking "Pokracovat" on one paused row
        could continue a different one and report the clicked row's cursor.

        It refuses rather than queues when the RUZ slot is taken. Every RUZ
        command claims the single global job before it may write company data,
        and a dispatch that meets a live job returns without doing anything --
        so saying "obnovenie bolo zaradene" then would be false, and the
        operator would wait for a resume that was never going to run.

        `running` is an accepted status, and it is the live-job check below --
        not the status -- that tells the two meanings of that word apart. With
        a job in the slot it is a run in progress and the operator gets told so;
        with nothing in the slot it is the wreck a SIGKILL or a mid-run deploy
        leaves, whose `failed` was never written because the process that would
        have written it is the one that died.
        """
        from registers.tasks import (
            resume_full_ruz_sync,
            resume_repair_sync,
            start_incremental_sync,
        )

        progress = SyncProgress.objects.get(pk=pk)
        if progress.status not in ['paused', 'failed', 'running']:
            messages.error(request, 'Synchronizaciu nie je mozne obnovit.')
            return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

        if progress.sync_type not in self.RESUMABLE_SYNC_TYPES:
            messages.error(
                request,
                f'{progress.get_sync_type_display()} zatial nema cestu na '
                f'obnovenie. Spusti ho znova prislusnym tlacidlom vyssie.'
            )
            return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

        live = _live_ruz_job()
        if live is not None:
            messages.warning(
                request,
                f'RUZ bezi ({live.get_job_type_display()} #{live.pk}, '
                f'{live.get_status_display()}). Obnovenie by teraz neurobilo nic; '
                f'skus to, ked dobehne.'
            )
            return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))

        try:
            if progress.sync_type == 'repair':
                resume_repair_sync.delay(progress_id=progress.pk)
            elif progress.sync_type == 'incremental':
                start_incremental_sync.delay()
            else:
                resume_full_ruz_sync.delay(progress_id=progress.pk)
            messages.success(
                request,
                f'{progress.get_sync_type_display()}: obnovenie bolo zaradene '
                f'od RUZ ID {progress.last_processed_ruz_id:,}.'
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
        # A repair claims the global RUZ slot, so while the walk runs this queue
        # is refused inside the task and nothing happens. Reporting it as
        # planned would be the false success `resume_sync_view` was fixed for.
        if _live_ruz_job() is not None:
            messages.warning(
                request,
                'RUZ bezi. Opravny Sync by teraz neurobil nic; skus to, ked dobehne.'
            )
            return HttpResponseRedirect(reverse('admin:registers_syncprogress_changelist'))
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


@admin.register(IndividualEntity)
class IndividualEntityAdmin(UnfoldModelAdmin):
    """Admin interface for natural persons and SZCO entities from RUZ."""

    list_display = [
        'ico', 'nazov_UJ', 'pravna_forma', 'mesto',
        'debt_status_display', 'vat_status_display', 'datum_poslednej_upravy'
    ]
    list_filter = [
        'pravna_forma', 'velkost_organizacie', 'kraj',
        ('debt_vszp', admin.EmptyFieldListFilter),
        ('debt_soc_poist', admin.EmptyFieldListFilter),
        ('tax_debt', admin.EmptyFieldListFilter),
        ('vat_payer', admin.EmptyFieldListFilter),
    ]
    search_fields = ['ico', 'nazov_UJ', 'mesto', 'sk_NACE']
    readonly_fields = [
        'ruz_id', 'last_insurance_debt', 'fs_update_date',
        'datum_poslednej_upravy',
        'debt_display', 'tax_display'
    ]

    fieldsets = (
        ('Základné údaje', {
            'fields': ('ruz_id', 'ico', 'dic', 'sid', 'nazov_UJ')
        }),
        ('Adresa', {
            'fields': ('ulica', 'mesto', 'psc', 'kraj', 'okres', 'sidlo'),
            'classes': ('collapse',)
        }),
        ('Podnikateľské údaje', {
            'fields': (
                'pravna_forma', 'sk_NACE', 'velkost_organizacie',
                'druh_vlastnictva', 'datum_zalozenia', 'datum_zrusenia'
            ),
            'classes': ('collapse',)
        }),
        ('Finančné vykazy', {
            'fields': ('id_uctovnych_zavierok', 'id_vyrocnych_sprav', 'uses_ifrs', 'konsolidovana'),
            'classes': ('collapse',)
        }),
        ('Dlhy - Poisťovne', {
            'fields': (
                'debt_display',
                'debt_vszp', 'debt_soc_poist',
                'social_listed_without_amount',
                'last_insurance_debt'
            )
        }),
        ('DPH - Finančná správa', {
            'fields': (
                'tax_display',
                'vat_payer', 'ic_dph', 'datum_reg_dph',
                'vat_deleted_date', 'vat_deleted_reason',
                'tax_reliability', 'fs_update_date', 'tax_debt', 'bank_accounts'
            ),
            'classes': ('collapse',)
        }),
        ('Zdroj dát', {
            'fields': ('zdroj_dat', 'datum_poslednej_upravy'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Dlhy (VSZP/SP)')
    def debt_display(self, obj):
        """Show formatted debt information."""
        parts = []
        if obj.debt_vszp:
            parts.append(f'VSZP: {obj.debt_vszp:,.2f} €')
        if obj.debt_soc_poist:
            parts.append(f'SP: {obj.debt_soc_poist:,.2f} €')
        elif obj.social_listed_without_amount:
            # "—" would say we know nothing here. We know something: the
            # register lists the company and published no sum for it.
            parts.append('SP: bez zverejnenej sumy')
        if not parts:
            return mark_safe('<span style="color: #999;">—</span>')
        return mark_safe('<br/>'.join(parts))

    @admin.display(description='Daňový dlh')
    def tax_display(self, obj):
        """Show tax debt."""
        if obj.tax_debt:
            return f'{obj.tax_debt:,.2f} €'
        return mark_safe('<span style="color: #999;">—</span>')

    @admin.display(description='Dlhy', ordering='debt_vszp')
    def debt_status_display(self, obj):
        """Show debt status badge."""
        if obj.debt_vszp or obj.debt_soc_poist:
            total = (obj.debt_vszp or 0) + (obj.debt_soc_poist or 0)
            return mark_safe(
                f'<span class="cf-badge cf-badge--danger">{total:,.0f} €</span>'
            )
        if obj.social_listed_without_amount:
            return mark_safe(
                '<span class="cf-badge cf-badge--warning" title="Sociálna '
                'poisťovňa uvádza spoločnosť v zozname dlžníkov bez zverejnenej '
                'sumy">SP bez sumy</span>'
            )
        return mark_safe(
            '<span class="cf-badge cf-badge--success">OK</span>'
        )

    @admin.display(description='DPH', ordering='vat_payer')
    def vat_status_display(self, obj):
        """Show VAT payer status."""
        if obj.vat_payer is True:
            return mark_safe(
                '<span class="cf-badge cf-badge--info">Plat.</span>'
            )
        elif obj.vat_payer is False:
            return mark_safe(
                '<span class="cf-badge cf-badge--idle">—</span>'
            )
        return mark_safe(
            '<span class="cf-badge cf-badge--muted">?</span>'
        )

