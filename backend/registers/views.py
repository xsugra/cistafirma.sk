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


def trigger_fetch_ruz_data(request):
    """
    A view to manually trigger the fetch_ruz_data_task.
    """
    fetch_ruz_data_task.delay()
    return JsonResponse({"message": "RUZ data fetching task has been triggered."})


def trigger_insurance_debt_data(request):
    """
    A view to manually trigger the force_check_all_companies_debts task for all companies.
    """
    force_check_all_companies_debts.delay()
    return JsonResponse({"message": "Insurance debt checking for all companies has been triggered."})


def trigger_fetch_fs_data(request):
    """
    A view to manually trigger the update_fs_data_task.
    """
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
            # Queue purge vymazala aj prípadné ORSR/financials tasky — znovu spustíme.
            schedule_missing_orsr_sync.delay(limit=limit)
            schedule_ruz_financials_sync.delay(
                limit=limit,
                eligible_only=False,
                missing_only=True,
            )
            messages.success(
                request,
                f"Focus mode aktivovaný: vypnutých {len(state.snapshot or [])} periodic taskov, "
                f"revoknutých {len(state.last_revoked or [])} bežiacich. "
                f"Queue purge hotový, znovu spustené ORSR + Financials (batch {limit}).",
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

