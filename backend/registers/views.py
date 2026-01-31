from django.http import JsonResponse
from .tasks import fetch_ruz_data_task, schedule_insurance_debt_checks, force_check_all_companies_debts, update_fs_data_task


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