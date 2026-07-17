"""``company_create`` — alta unitaria de una empresa L1 + su base (SOL-091, T-091-06).

Adapter de I/O (thin) sobre ``service.db.provision_company_database``: registra
(idempotente) la ``Company`` L0 y provisiona su base ``company_<id>_db``. El
gate de autorización (``platform.provision``) aplica a los endpoints HTTP; una
management command depende del acceso OS a ``manage.py`` + del guard
``ensure_management_enabled`` (``MULTIDB_MANAGEMENT_ENABLED``) — mismo criterio
que Odoo separa CLI vs RPC (== ``company_migrate_all``).
"""
from django.core.management.base import BaseCommand

from addons.company.models import Company
from orm.routers import company_db_alias
from service.db import provision_company_database


class Command(BaseCommand):
    help = 'Registra una empresa L1 (idempotente) y provisiona su base company_<id>_db.'

    def add_arguments(self, parser):
        parser.add_argument('code', help='Código (slug) único de la empresa.')
        parser.add_argument(
            '--name', default=None,
            help='Nombre de la empresa (por defecto, el código).',
        )

    def handle(self, *args, **options):
        code = options['code']
        company, row_created = Company.objects.get_or_create(
            code=code, defaults={'name': options.get('name') or code},
        )
        db_name = company_db_alias(company.id)
        db_name, db_created = provision_company_database(db_name)
        self.stdout.write(
            'company=%s id=%s db=%s row_created=%s db_created=%s'
            % (code, company.id, db_name, row_created, db_created)
        )
