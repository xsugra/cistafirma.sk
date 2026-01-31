from django.core.management.base import BaseCommand
from registers.tasks import force_check_all_companies_debts

class Command(BaseCommand):
    help = 'Manuálne spustí okamžitú kontrolu dlhov v poisťovniach pre všetky firmy v databáze.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Odosielam požiadavku na kontrolu dlhov pre všetky firmy...'))

        # Zavoláme našu novú Celery úlohu.
        # .delay() ju pošle na spracovanie workerom na pozadí.
        task = force_check_all_companies_debts.delay()

        self.stdout.write(
            self.style.SUCCESS(
                f'Úloha úspešne odoslaná na spracovanie (Task ID: {task.id}). '
                f'Sledujte logy Celery workera pre detailný priebeh.'
            )
        )
