from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from companies.models import Company, CompanyFinancialResult
from registers.eligibility import ORSR_ELIGIBLE_LEGAL_FORMS
from registers.models import OrsrCompanyProfile
from registers.services import focus_mode as focus_mode_service

from .tasks import (
    fetch_ruz_data_task,
    force_check_all_companies_debts,
    schedule_missing_orsr_sync,
    schedule_ruz_financials_sync,
    update_fs_data_task,
)


@staff_member_required
@require_http_methods(["POST"])
def trigger_fetch_ruz_data(request):
    """Legacy endpoint — prefer POST /api/admin/sync/jobs/ {"job_type":"ruz_full"}."""
    from registers.services.sync_engine import enqueue_ruz_job

    job, created = enqueue_ruz_job(
        job_type="ruz_incremental",
        triggered_by_id=request.user.id,
        triggered_via="admin_ui",
    )
    if created:
        result = fetch_ruz_data_task.apply_async(kwargs={"sync_job_id": job.pk})
        job.celery_task_id = result.id or ""
        job.save(update_fields=["celery_task_id"])
    return JsonResponse({
        "message": "RUZ data fetching task has been triggered." if created else "RUZ sync is already active.",
        "job_id": job.pk,
        "created": created,
    })


@staff_member_required
@require_http_methods(["POST"])
def trigger_insurance_debt_data(request):
    """Legacy endpoint — prefer POST /api/admin/sync/jobs/ {"job_type":"insurance_batch"}."""
    force_check_all_companies_debts.delay()
    return JsonResponse({"message": "Insurance debt checking for all companies has been triggered."})


@staff_member_required
@require_http_methods(["POST"])
def trigger_fetch_fs_data(request):
    """Legacy endpoint — prefer POST /api/admin/sync/jobs/ {"job_type":"fs_update"}."""
    update_fs_data_task.delay()
    return JsonResponse({"message": "FS data update task has been triggered."})


@staff_member_required
@require_http_methods(["GET", "POST"])
def sync_dashboard(request):
    """Simple staff page to manually trigger ORSR + financial sync and inspect quick progress."""
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            limit = int(request.POST.get("limit", "200"))
        except ValueError:
            limit = 200
        limit = max(1, min(limit, 500000))

        if action == "start_full_manual_sync":
            schedule_missing_orsr_sync.delay(limit=limit)
            schedule_ruz_financials_sync.delay(
                limit=limit,
                eligible_only=False,
                missing_only=True,
            )
            messages.success(
                request,
                f"Spustené: ORSR + hospodárske výsledky pre dávku {limit} firiem.",
            )
        elif action == "start_orsr_only":
            schedule_missing_orsr_sync.delay(limit=limit)
            messages.success(request, f"Spustené: ORSR sync pre dávku {limit} firiem.")
        elif action == "start_financials_only":
            schedule_ruz_financials_sync.delay(
                limit=limit,
                eligible_only=False,
                missing_only=True,
            )
            messages.success(request, f"Spustené: Financials sync pre dávku {limit} firiem.")
        elif action == "enter_focus_mode":
            state = focus_mode_service.enter_focus_mode(request.user)
            messages.success(
                request,
                f"Focus mode aktivovaný: vypnutých {len(state.snapshot or [])} periodic taskov, "
                "existujúce synchronizačné úlohy zostali zachované a dobehnú.",
            )
        elif action == "exit_focus_mode":
            focus_mode_service.exit_focus_mode(request.user)
            messages.success(request, "Focus mode deaktivovaný, periodic tasky obnovené.")
        else:
            messages.error(request, "Neznáma akcia.")

        return redirect("registers_sync_dashboard")

    eligible = Company.objects.filter(
        pravna_forma__in=ORSR_ELIGIBLE_LEGAL_FORMS,
        datum_zrusenia__isnull=True,
    )

    eligible_ids = eligible.values("id")
    with_financials = CompanyFinancialResult.objects.values("company_id").distinct().count()
    eligible_total = eligible.count()
    all_companies_total = Company.objects.count()
    missing_financials = max(0, all_companies_total - with_financials)

    context = {
        "eligible_total": eligible_total,
        "missing_orsr": eligible.filter(orsr_profile__isnull=True).count(),
        "with_orsr": OrsrCompanyProfile.objects.filter(company_id__in=eligible_ids).count(),
        "with_financials": with_financials,
        "missing_financials": missing_financials,
        "latest_orsr": OrsrCompanyProfile.objects.select_related("company").order_by("-last_synced_at")[:10],
        "latest_financial_rows": CompanyFinancialResult.objects.select_related("company").order_by("-updated_at")[:10],
        "focus_mode": focus_mode_service.focus_mode_status(),
    }
    return render(request, "registers/sync_dashboard.html", context)


# ============================================================================
# REST API ViewSets for SZCO/Individual Entities
# ============================================================================
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import IndividualEntity
from .serializers import IndividualEntityListSerializer, IndividualEntityDetailSerializer


class IndividualEntityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API ViewSet for IndividualEntity (SZCO/natural persons).

    Endpoints:
    - GET /api/individuals/ - List all individuals with filtering
    - GET /api/individuals/{id}/ - Get individual details

    Filtering:
    - Search by ICO, name: ?search=...
    - Filter by legal form: ?pravna_forma=100
    - Filter by city: ?mesto=...
    - Filter by debt status: ?debt_status__isnull=False
    """

    queryset = IndividualEntity.objects.all().order_by('-datum_poslednej_upravy')
    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter
    ]
    filterset_fields = [
        'pravna_forma', 'velkost_organizacie', 'kraj',
        'vat_payer', 'debt_vszp', 'debt_soc_poist', 'tax_debt'
    ]
    search_fields = ['ico', 'nazov_UJ', 'mesto', 'sk_NACE']
    ordering_fields = ['ico', 'nazov_UJ', 'datum_poslednej_upravy', 'debt_vszp']
    ordering = ['-datum_poslednej_upravy']

    def get_serializer_class(self):
        """Use detail serializer only for retrieve action."""
        if self.action == 'retrieve':
            return IndividualEntityDetailSerializer
        return IndividualEntityListSerializer
