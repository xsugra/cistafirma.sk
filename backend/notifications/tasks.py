from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(queue='celery')
def send_pending_notifications():
    """Send all pending notification emails. Runs every 15 minutes via Celery Beat."""
    from .services import send_pending_email_notifications
    sent = send_pending_email_notifications()
    logger.info('Sent %d notification emails', sent)
    return f'Sent {sent} notification emails'
