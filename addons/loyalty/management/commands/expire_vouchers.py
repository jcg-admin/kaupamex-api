from addons.base.management.unit_of_work import UnitOfWorkCommand
from addons.loyalty.tasks import expire_vouchers


class Command(UnitOfWorkCommand):
    help = 'UC-SYS-02: desactiva vouchers vencidos (cron cada hora)'

    def handle(self, *args, **options):
        count = expire_vouchers()
        self.stdout.write(f'expire_vouchers: {count} vouchers expirados.')
