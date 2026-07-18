"""Servicios del addon ``product_expiry`` — cálculo de fechas + FEFO + alertas.

Réplica fiel de los compute/cron de Odoo ``product_expiry`` (idéntico en 18 y
19), adaptados a funciones (el orquestador llama estos servicios donde Odoo
usaba ``@api.depends`` / ``ir.cron``).

- ``compute_lot_dates`` — ``_compute_expiration_date`` + ``_compute_dates``
  (``production_lot.py:34-72``): fija ``expiration_date`` = ahora + ``expiration_time``
  días desde la config del producto, y ``use/removal/alert_date`` = caducidad −
  ``use/removal/alert_time`` días.
- ``fefo_gather`` — ``_get_removal_strategy_order`` (``stock_quant.py:24-28``):
  la estrategia ``fefo`` ordena por ``removal_date, in_date, id``.
- ``alert_date_exceeded`` — ``_alert_date_exceeded`` (``production_lot.py:74-104``):
  marca ``product_expiry_reminded`` en lotes cuya ``alert_date`` venció y que
  tienen existencia a la mano en ubicaciones internas.
"""
from datetime import timedelta

from django.utils import timezone

from addons.product_expiry.models import StockLotExpiry
from addons.stock.models import StockLocation, StockQuant


def compute_lot_dates(lot):
    """Calcula/actualiza las fechas de caducidad del lote (Odoo _compute_*).

    Lee la config de caducidad del producto (``ProductExpiryConfig``). Si el
    producto no usa fechas de caducidad, limpia todas las fechas. Devuelve el
    ``StockLotExpiry`` (creándolo si hace falta).
    """
    expiry, _ = StockLotExpiry.objects.get_or_create(lot=lot)
    config = getattr(lot.product, 'expiry_config', None)
    if config is None or not config.use_expiration_date:
        expiry.expiration_date = None
        expiry.use_date = None
        expiry.removal_date = None
        expiry.alert_date = None
        expiry.save(update_fields=[
            'expiration_date', 'use_date', 'removal_date', 'alert_date', 'updated_at'])
        return expiry
    # _compute_expiration_date: caducidad = ahora + expiration_time días.
    if not expiry.expiration_date:
        expiry.expiration_date = timezone.now() + timedelta(days=config.expiration_time)
    # _compute_dates: use/removal/alert = caducidad − use/removal/alert_time días.
    expiry.use_date = expiry.expiration_date - timedelta(days=config.use_time)
    expiry.removal_date = expiry.expiration_date - timedelta(days=config.removal_time)
    expiry.alert_date = expiry.expiration_date - timedelta(days=config.alert_time)
    expiry.save(update_fields=[
        'expiration_date', 'use_date', 'removal_date', 'alert_date', 'updated_at'])
    return expiry


def fefo_gather(product, location):
    """Quants del producto en ``location`` ordenados por FEFO (Odoo 'fefo').

    Orden ``removal_date, in_date, id`` (``_get_removal_strategy_order``): el
    lote que caduca/se retira primero sale primero. Los quants sin lote (sin
    ``removal_date``) quedan ordenados por ``in_date`` como fallback.
    """
    return (
        StockQuant.objects
        .filter(product=product, location=location, quantity__gt=0)
        .order_by('lot__expiry__removal_date', 'in_date', 'id')
    )


def alert_date_exceeded():
    """Marca ``product_expiry_reminded`` en lotes con alerta vencida (Odoo cron).

    Réplica de ``_alert_date_exceeded``: selecciona lotes cuya ``alert_date`` ya
    venció, que aún no fueron notificados y que tienen existencia (> 0) en
    ubicaciones internas; los marca como notificados. Devuelve la lista de
    ``StockLotExpiry`` marcados.

    Adaptación acotada (no fabricación): Odoo agenda además una
    ``mail.activity`` sobre el responsable del producto. Este proyecto no tiene
    el chatter de Odoo (``mail.thread``/``mail.activity``), así que la
    notificación se reduce al flag idempotente ``product_expiry_reminded``.
    """
    now = timezone.now()
    candidates = StockLotExpiry.objects.filter(
        alert_date__lte=now, product_expiry_reminded=False,
    ).exclude(alert_date__isnull=True)
    marked = []
    for expiry in candidates:
        has_internal_stock = StockQuant.objects.filter(
            lot=expiry.lot, quantity__gt=0,
            location__usage=StockLocation.USAGE_INTERNAL,
        ).exists()
        if has_internal_stock:
            expiry.product_expiry_reminded = True
            expiry.save(update_fields=['product_expiry_reminded', 'updated_at'])
            marked.append(expiry)
    return marked
