"""
import_catalog_oja — importa el catálogo real de OJA Yoruba.

Lee /tmp/catalogo/oja/productos/ (o --catalog-dir) y crea/actualiza:
  - Category     : 8 categorías basadas en las carpetas del catálogo
  - Product      : 256 productos con is_published=True, stock=1
  - ProductImage : hasta 322 imágenes copiadas a MEDIA_ROOT/products/images/

Idempotente: update_or_create / get_or_create en todos los modelos.
La segunda ejecución no produce cambios en BD ni duplicados.

Decisiones aprobadas (DEC-OJA-01..05):
  DEC-OJA-01: usa settings.MEDIA_ROOT (lee del .env del entorno)
  DEC-OJA-02: SKU = 'OJA-' + slug[:40]
  DEC-OJA-03: no importa ProductDiscount (solo precio_actual)
  DEC-OJA-04: stock=1 en todos los productos (stock_disponible es NULL)
  DEC-OJA-05: trunca descripcion en 'Recibelo:' o 'Valoraciones'

Uso:
  python manage.py import_catalog_oja
  python manage.py import_catalog_oja --dry-run
  python manage.py import_catalog_oja --category=collares-y-pulseras
"""
import json
import shutil
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalogue.models import Category, Product, ProductImage

CATEGORIA_NAMES = {
    'akoses-medicinas': 'Akoses / Medicinas',
    'collares-de-orumila': 'Collares de Orumila',
    'collares-y-pulseras': 'Collares y Pulseras',
    'complementos-y-herramientas': 'Complementos y Herramientas',
    'enseres': 'Ingredientes Rituales',
    'isan-iconos': 'Isan / Iconos',
    'lo-nuevo': 'Lo Nuevo',
    'ropa-y-telas': 'Ropa y Telas',
}

# Folder slug → DB slug when they differ (folder name ≠ semantic category name)
SLUG_OVERRIDES = {
    'enseres': 'ingredientes-rituales',
}

_CORTE = ('Recibelo:', 'Valoraciones', 'Información adicional')


def _limpiar_descripcion(texto):
    if not texto:
        return ''
    for marcador in _CORTE:
        idx = texto.find(marcador)
        if idx != -1:
            texto = texto[:idx]
    return texto.strip()


class Command(BaseCommand):
    help = 'Importa el catálogo OJA Yoruba desde /tmp/catalogo/oja/productos/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué se importaría sin escribir en BD ni filesystem',
        )
        parser.add_argument(
            '--catalog-dir', default='/tmp/catalogo/oja/productos/',
            help='Path al directorio del catálogo (default: /tmp/catalogo/oja/productos/)',
        )
        parser.add_argument(
            '--category',
            help='Importar solo esta categoría (slug, ej. collares-y-pulseras)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        catalog_dir = Path(options['catalog_dir'])
        filter_category = options.get('category')

        stats = dict(
            cat_created=0, cat_updated=0,
            prod_created=0, prod_updated=0,
            img_created=0, img_updated=0,
            errors=0,
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — sin cambios en BD ni filesystem'))

        if not catalog_dir.exists():
            self.stderr.write(self.style.ERROR(f'Directorio no encontrado: {catalog_dir}'))
            return

        media_images = Path(settings.MEDIA_ROOT) / 'products' / 'images'
        if not dry_run:
            media_images.mkdir(parents=True, exist_ok=True)

        for cat_dir in sorted(catalog_dir.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith('_'):
                continue
            cat_slug = cat_dir.name
            if cat_slug not in CATEGORIA_NAMES:
                continue
            if filter_category and cat_slug != filter_category:
                continue

            category = self._import_category(cat_slug, dry_run, stats)

            for prod_dir in sorted(cat_dir.iterdir()):
                if not prod_dir.is_dir():
                    continue
                data_file = prod_dir / 'data.json'
                if not data_file.exists():
                    continue
                try:
                    with open(data_file, encoding='utf-8') as f:
                        data = json.load(f)
                    self._import_product(data, category, prod_dir, media_images, dry_run, stats)
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f'Error en {prod_dir.name}: {exc}'))
                    stats['errors'] += 1

        self._print_summary(stats, dry_run)

    def _import_category(self, slug, dry_run, stats):
        name = CATEGORIA_NAMES[slug]
        db_slug = SLUG_OVERRIDES.get(slug, slug)
        if dry_run:
            stats['cat_created'] += 1
            return _DryRunCategory(slug=db_slug, name=name)
        cat, created = Category.objects.get_or_create(
            slug=db_slug,
            defaults={'name': name, 'is_active': True},
        )
        if created:
            stats['cat_created'] += 1
            self.stdout.write(f'  [+] Categoría: {name}')
        else:
            stats['cat_updated'] += 1
        return cat

    def _import_product(self, data, category, prod_dir, media_images, dry_run, stats):
        slug = data['slug']
        nombre = (data.get('nombre') or '')[:200]
        descripcion = _limpiar_descripcion(data.get('descripcion') or '')
        precio = Decimal(str(data['precio_actual'])).quantize(Decimal('0.01'))
        sku = f'OJA-{slug[:40]}'
        imagenes = data.get('imagenes') or []

        if dry_run:
            stats['prod_created'] += 1
            stats['img_created'] += len(imagenes)
            return

        product, created = Product.objects.update_or_create(
            slug=slug,
            defaults={
                'name': nombre,
                'sku': sku,
                'description': descripcion,
                'short_description': nombre[:300],
                'price': precio,
                'stock': 1,
                'is_active': True,
                'is_published': True,
            },
        )
        # UC-CAT-13: M2M — assign category after save (can't pass to create()).
        product.categories.add(category)
        if created:
            stats['prod_created'] += 1
        else:
            stats['prod_updated'] += 1

        for idx, img_data in enumerate(imagenes):
            archivo = (img_data or {}).get('archivo')
            if not archivo:
                continue
            src = prod_dir / 'images' / archivo
            if src.exists():
                shutil.copy2(str(src), str(media_images / archivo))
            ProductImage.objects.update_or_create(
                product=product,
                order=idx,
                defaults={
                    'image': f'products/images/{archivo}',
                    'alt_text': nombre[:200],
                    'is_cover': idx == 0,
                },
            )
            if idx == 0:
                stats['img_created'] += 1
            else:
                stats['img_updated'] += 1

    def _print_summary(self, stats, dry_run):
        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Categorías: {stats["cat_created"]} creadas, '
            f'{stats["cat_updated"]} actualizadas'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Productos:  {stats["prod_created"]} creados, '
            f'{stats["prod_updated"]} actualizados'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Imágenes:   {stats["img_created"]} + {stats["img_updated"]} '
            f'(primeras + adicionales)'
        ))
        if stats['errors']:
            self.stdout.write(self.style.ERROR(f'{prefix}Errores:    {stats["errors"]}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'{prefix}Errores:    0'))


class _DryRunCategory:
    """Objeto placeholder para dry-run (sin acceso a BD)."""
    def __init__(self, slug, name):
        self.slug = slug
        self.name = name
        self.pk = None
