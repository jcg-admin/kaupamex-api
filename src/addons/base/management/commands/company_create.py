"""``company_create`` — alta unitaria de una empresa L1 + su base (SOL-091, T-091-06).

Adapter de I/O (thin) sobre ``service.db.provision_company_database``: registra
(idempotente) la ``ResCompany`` y provisiona su base ``company_<id>_db``. El
gate de autorización (``platform.provision``) aplica a los endpoints HTTP; una
management command depende del acceso OS a ``manage.py`` + del guard
``ensure_management_enabled`` (``MULTIDB_MANAGEMENT_ENABLED``) — mismo criterio
que Odoo separa CLI vs RPC (== ``company_migrate_all``).
"""
from django.core.management.base import BaseCommand, CommandError

from addons.base.models import CompanySetting, ResCompany
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
        parser.add_argument(
            '--setting', action='append', default=[], metavar='CLAVE=VALOR',
            help=(
                'CompanySetting per-empresa a sembrar (repetible). Es el canal '
                'para los remitentes de correo del L1 — antes constantes de '
                'código (DEC-3, tenants-sin-clases-en-codigo). Ejemplo: '
                '--setting notifications.from_email=noreply@ejemplo.com'
            ),
        )

    def handle(self, *args, **options):
        code = options['code']
        pairs = [_parse_setting(raw) for raw in options['setting']]
        # ``name`` vive en el partner (related); el manager fabrica el
        # partner al crear, como el ``create`` de la fuente.
        company = ResCompany.objects.filter(code=code).first()
        row_created = company is None
        if row_created:
            company = ResCompany.create_company(
                options.get('name') or code, code=code)
        # ``company_id=<pk>`` escalar, no la instancia: asignar la instancia
        # dispara el descriptor de la FK, que consulta el router multi-DB sin
        # ``company_scope`` activo y revienta con ``CompanyContextRequired``.
        settings_created = 0
        for key, value in pairs:
            _, created = CompanySetting.objects.get_or_create(
                company_id=company.pk, key=key, defaults={'value': value})
            settings_created += int(created)
        db_name = company_db_alias(company.id)
        db_name, db_created = provision_company_database(db_name)
        self.stdout.write(
            'company=%s id=%s db=%s row_created=%s db_created=%s settings_created=%s'
            % (code, company.id, db_name, row_created, db_created, settings_created)
        )


def _parse_setting(raw):
    """``clave=valor`` → ``(clave, valor)``; falla ruidoso si no lo es."""
    key, sep, value = raw.partition('=')
    if not sep or not key.strip():
        raise CommandError(
            '--setting espera CLAVE=VALOR, recibido: %r' % raw)
    return key.strip(), value
