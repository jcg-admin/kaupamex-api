"""``company_migrate_all`` — migra todas las bases ``company_<N>_db`` (SOL-091).

Orquesta ``service.db.migrate_all_company_databases`` (T-091-06). El gate de
autorización (``platform.provision``) aplica a los **endpoints HTTP**; una
management command depende del acceso OS a ``manage.py`` + del guard
``ensure_management_enabled`` (``MULTIDB_MANAGEMENT_ENABLED``) — mismo criterio
que Odoo separa CLI vs RPC.
"""
from django.core.management.base import BaseCommand, CommandError

from service.db import migrate_all_company_databases


class Command(BaseCommand):
    help = 'Aplica migraciones a todas las bases company_<N>_db (o a --names).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--names',
            nargs='*',
            default=None,
            help='Bases concretas; por defecto descubre las company_<N>_db.',
        )

    def handle(self, *args, **options):
        results = migrate_all_company_databases(names=options.get('names'))
        failed = [r for r in results if r['status'] == 'failed']
        for r in results:
            line = '%s: %s' % (r['db'], r['status'])
            if r['error']:
                line += ' — %s' % r['error']
            self.stdout.write(line)
        self.stdout.write('OK: %d, FAILED: %d' % (len(results) - len(failed), len(failed)))
        if failed:
            raise CommandError('%d base(s) fallaron la migracion' % len(failed))
