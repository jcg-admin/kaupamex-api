"""
purge_logs — envoltura de CLI sobre ``IrLogging._purge_expired``.

La retención de DEC-LOG-05 la aplica hoy el **barrido**: el método lleva
``@api.autovacuum`` y lo invoca ``ir.autovacuum`` desde el único cron de
recolección (``base.0032``), no un job propio como hasta H-API-747.

Este comando se conserva como **entrada manual**, y sigue siendo el único
camino para ``--dry-run``: el colector invoca sin argumentos, así que la purga
programada siempre borra. Ver qué se borraría antes de que ocurra es una
operación de humano, y retirarla habría dejado esa capacidad sin reemplazo —
por eso el mapa de disolución de ``observability`` se corrigió: el comando no
desaparece, **se muda** al addon dueño del modelo (H-API-752).

    ./kaupamex-bin purge_logs --dry-run
    ./kaupamex-bin purge_logs
"""
from django.core.management.base import BaseCommand

from addons.base.models import IrLogging


class Command(BaseCommand):
    help = (
        'Purga IrLogging por retencion (DEC-LOG-05). BusinessEvent '
        'no se toca. El ciclo normal lo corre el barrido de ir.autovacuum; '
        'esto es la entrada manual.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No borra; solo reporta cuantas filas se purgarian.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        conteos = IrLogging._purge_expired(dry_run=dry)

        prefijo = '[dry-run] ' if dry else ''
        for etiqueta, n in conteos.items():
            self.stdout.write(f'{prefijo}{etiqueta}: {n} filas '
                              f'{"a purgar" if dry else "purgadas"}')
        total = sum(conteos.values())
        self.stdout.write(self.style.SUCCESS(
            f'{prefijo}Total: {total} filas '
            f'{"a purgar" if dry else "purgadas"}'))
