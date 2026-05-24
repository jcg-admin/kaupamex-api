"""Inventory tasks — apps.inventory (UC-SYS-03)."""
import logging

from apps.settings_app.models import SiteSettings
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from .services import _maybe_create_alert

logger = logging.getLogger('apps')


def scan_low_stock():
    threshold = SiteSettings.get_current().min_stock_threshold
    count = 0
    for product in Product.objects.filter(stock__lte=threshold):
        _maybe_create_alert(product, None, product.stock)
        count += 1
    for variant in (
        ProductVariant.objects
        .filter(stock__lte=threshold)
        .select_related('product', 'option')
    ):
        _maybe_create_alert(variant.product, variant, variant.stock)
        count += 1
    if count:
        logger.info('scan_low_stock: %d items escaneados bajo umbral.', count)
    return count


def run_product_import(job_id: int) -> None:
    """UC-INV-05: proceso síncrono de importación CSV (sin broker)."""
    import csv
    import io
    from .models import ImportJob
    from apps.catalogue.models import Category, Product

    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        logger.error('run_product_import: job %s no encontrado.', job_id)
        return

    job.status = ImportJob.STATUS_RUNNING
    job.save(update_fields=['status'])

    errors = []
    imported = 0
    total = 0

    try:
        job.file.seek(0)
        reader = csv.DictReader(io.TextIOWrapper(job.file, encoding='utf-8'))
        rows = list(reader)
        total = len(rows)

        for i, row in enumerate(rows, start=1):
            try:
                category_slug = (row.get('category') or '').strip()
                category = Category.objects.filter(slug=category_slug).first() if category_slug else None
                Product.objects.update_or_create(
                    sku=row['sku'].strip(),
                    defaults={
                        'name':        row.get('name', '').strip(),
                        'description': row.get('description', '').strip(),
                        'price':       row.get('price', 0),
                        'category':    category,
                        'is_active':   True,
                    },
                )
                imported += 1
            except Exception as exc:
                errors.append({'row': i, 'error': str(exc)})

        job.status        = ImportJob.STATUS_DONE
        job.total_rows    = total
        job.imported_rows = imported
        job.failed_rows   = len(errors)
        job.errors        = errors or None
    except Exception as exc:
        job.status = ImportJob.STATUS_FAILED
        job.errors = [{'row': 0, 'error': str(exc)}]

    job.save(update_fields=['status', 'total_rows', 'imported_rows', 'failed_rows', 'errors'])
