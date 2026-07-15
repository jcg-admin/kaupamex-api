from django.core.management.base import BaseCommand
from apps.inventory.tasks import scan_low_stock


class Command(BaseCommand):
    help = 'UC-SYS-03: escanea items con stock bajo umbral (cron cada 24h)'

    def handle(self, *args, **options):
        count = scan_low_stock()
        self.stdout.write(f'scan_low_stock: {count} items escaneados.')
