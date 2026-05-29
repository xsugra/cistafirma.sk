import logging

from celery import Task

from companies.models import Company

logger = logging.getLogger(__name__)


class BaseSyncTask(Task):
    abstract = True
    max_retries = 3
    default_retry_delay = 60
    autoretry_for = (Exception,)
    dont_autoretry_for = (Company.DoesNotExist,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Task %s[%s] failed permanently: %s",
            self.name, task_id, exc,
            exc_info=einfo,
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "Task %s[%s] retrying (%s/%s): %s",
            self.name, task_id, self.request.retries, self.max_retries, exc,
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)
