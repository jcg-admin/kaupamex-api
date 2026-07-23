"""Carga el Catálogo Nacional de Códigos Postales (SEPOMEX) en
``catalog_postal_code`` (SOL-016, DEC-02, tarea T-206).

El dataset oficial de Correos de México se versiona en el repo ``db``
(``provisioners/mariadb/data/sepomex-codigos-postales.txt``). Gotchas PROVEN:

- Encoding **ISO-8859-1 (latin-1)** — NO UTF-8 (los acentos se corromperían).
- Terminador **CRLF**; se hace strip del ``\r``.
- Línea 1 = nota de licencia, línea 2 = cabecera; ambas se descartan.
- Separador ``|`` (pipe), 15 columnas.

Licencia (Correos de México): el catálogo es de uso particular, no comercial,
no redistribuible.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from addons.base_address_extended.models import CatalogPostalCode

# Orden oficial de columnas del .txt SEPOMEX -> campos del modelo.
_FIELDS = [
    'postal_code', 'settlement_name', 'settlement_type', 'municipality',
    'state', 'city', 'office_postal_code', 'state_code', 'office_code',
    'postal_code_internal_code', 'settlement_type_code', 'municipality_code',
    'settlement_consecutive_id', 'zone', 'city_code',
]
_DEFAULT_PATH = '/home/user/e-commerce-db/provisioners/mariadb/data/sepomex-codigos-postales.txt'


class Command(BaseCommand):
    help = 'Carga el catálogo SEPOMEX de códigos postales en catalog_postal_code.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', default=_DEFAULT_PATH,
            help='Ruta al .txt oficial SEPOMEX (default: dataset versionado en db).',
        )
        parser.add_argument(
            '--batch-size', type=int, default=5000,
            help='Tamaño de lote para bulk_create (default 5000).',
        )
        parser.add_argument(
            '--truncate', action='store_true',
            help='Vacía la tabla antes de cargar (recarga limpia).',
        )

    def handle(self, *args, **options):
        path = Path(options['path'])
        if not path.exists():
            raise CommandError(f'No existe el dataset SEPOMEX en: {path}')

        batch_size = options['batch_size']

        if options['truncate']:
            deleted, _ = CatalogPostalCode.objects.all().delete()
            self.stdout.write(f'Tabla vaciada ({deleted} filas eliminadas).')

        with path.open(encoding='latin-1') as fh:
            lines = fh.read().split('\n')

        # Línea 0 = licencia, línea 1 = cabecera; el resto son datos.
        rows = []
        skipped = 0
        for raw in lines[2:]:
            line = raw.rstrip('\r')
            if not line.strip():
                continue
            parts = line.split('|')
            if len(parts) != 15:
                skipped += 1
                continue
            rows.append(CatalogPostalCode(**dict(zip(_FIELDS, parts))))

        with transaction.atomic():
            CatalogPostalCode.objects.bulk_create(rows, batch_size=batch_size)

        total = CatalogPostalCode.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'SEPOMEX cargado: {len(rows)} filas insertadas '
            f'({skipped} malformadas omitidas). Total en tabla: {total}.'
        ))
