"""
purge_logs — envoltura de CLI sobre ``IrLogging.purge_expired``.

La retención de DEC-LOG-05 la aplica el **cron** ``ir_cron_observability_purge``.
La lógica vive en el modelo —``addons.base.models.IrLogging.
purge_expired``— porque ``ir.cron`` invoca ``<model>.<method>()`` y no sabe
ejecutar comandos de Django.

Este comando se conserva como **entrada manual**, y además es el único camino
para ``--dry-run``: el runner del cron invoca sin argumentos, así que la purga
programada siempre borra. Ver qué se borraría antes de que ocurra es una
operación de humano.

    python manage.py purge_logs --dry-run
    python manage.py purge_logs
"""
from django.core.management.base import BaseCommand

from addons.base.models import IrLogging


class Command(BaseCommand):
    help = (
        'Purga IrLogging por retencion (DEC-LOG-05). BusinessEvent '
        'no se toca. El ciclo normal lo corre el cron '
        'ir_cron_observability_purge; esto es la entrada manual.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No borra; solo reporta cuantas filas se purgarian.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        conteos = IrLogging.purge_expired(dry_run=dry)

        prefijo = '[dry-run] ' if dry else ''
        for etiqueta, n in conteos.items():
            self.stdout.write(f'{prefijo}{etiqueta}: {n} filas '
                              f'{"a purgar" if dry else "purgadas"}')
        total = sum(conteos.values())
        self.stdout.write(self.style.SUCCESS(
            f'{prefijo}Total: {total} filas '
            f'{"a purgar" if dry else "purgadas"}'))
