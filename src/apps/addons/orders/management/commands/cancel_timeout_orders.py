from django.core.management.base import BaseCommand
from apps.addons.orders.tasks import cancel_timeout_orders


class Command(BaseCommand):
    help = 'UC-SYS-01: cancela ordenes PENDING por timeout de pago (cron cada 5 min)'

    def handle(self, *args, **options):
        count = cancel_timeout_orders()
        self.stdout.write(f'cancel_timeout_orders: {count} ordenes canceladas.')
