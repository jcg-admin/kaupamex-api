from django.core.management.base import BaseCommand
from apps.modules.voucher.tasks import expire_vouchers


class Command(BaseCommand):
    help = 'UC-SYS-02: desactiva vouchers vencidos (cron cada hora)'

    def handle(self, *args, **options):
        count = expire_vouchers()
        self.stdout.write(f'expire_vouchers: {count} vouchers expirados.')
