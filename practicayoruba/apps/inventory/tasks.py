"""
Celery tasks — apps.inventory (UC-SYS-03).

scan_low_stock: barrido periodico de productos y variantes con
stock <= umbral. Complementa el path inline de _maybe_create_alert
(llamado en cada decremento/ajuste de InventoryService) cubriendo
los casos donde el stock baja por ajuste manual sin transaccion de
venta (UC-INV-04 sin trigger inline de alerta).
Se registra en Celery Beat (cada 24h).
"""
import logging

from celery import shared_task

from apps.settings_app.models import SiteSettings
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant
from .services import _maybe_create_alert

logger = logging.getLogger('apps')


@shared_task(name='inventory.scan_low_stock')
def scan_low_stock():
    """UC-SYS-03 path periodico: escanea stock bajo umbral."""
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
