"""Modelo ``StockLotExpiry`` — addon ``product_expiry``.

Adaptación fiel de Odoo ``product_expiry`` sobre ``stock.lot``
(``product_expiry/models/production_lot.py:8-38``, idéntico en 18 y 19): las
fechas de caducidad del lote. En Odoo son campos ``_inherit`` inyectados en
``stock.lot``; por DEC-SALE-01 se materializan como modelo RELATED OneToOne al
``stock.StockLot`` base.

- ``expiration_date`` (o18:14) — fecha de caducidad. La usa ``product_expiry_alert``.
- ``use_date`` (o18:17) — consumo preferente (best before).
- ``removal_date`` (o18:19) — fecha de retiro; clave de la estrategia FEFO.
- ``alert_date`` (o18:21) — fecha para el filtro de alertas de caducidad.
- ``product_expiry_alert`` (o18:22) — computado: la caducidad ya se alcanzó.
- ``product_expiry_reminded`` (o18:23) — la alerta ya se notificó (idempotencia).

El cálculo de las fechas (``services.compute_lot_dates``) y el barrido de
alertas (``services.alert_date_exceeded``) replican los compute/cron de Odoo.
"""
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class StockLotExpiry(TimeStampedModel):
    """``stock.lot`` caducidad — fechas del lote (Odoo product_expiry)."""

    lot                     = models.OneToOneField(
        'stock.StockLot', on_delete=models.CASCADE, related_name='expiry',
        help_text='Lote base (Odoo stock.lot).',
    )
    expiration_date         = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha de caducidad (Odoo expiration_date).',
    )
    use_date                = models.DateTimeField(
        null=True, blank=True,
        help_text='Consumo preferente / best before (Odoo use_date).',
    )
    removal_date            = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha de retiro; clave FEFO (Odoo removal_date).',
    )
    alert_date              = models.DateTimeField(
        null=True, blank=True,
        help_text='Fecha de alerta de caducidad (Odoo alert_date).',
    )
    product_expiry_reminded = models.BooleanField(
        default=False,
        help_text='La alerta ya se notificó (Odoo product_expiry_reminded).',
    )

    class Meta:
        db_table = 'stock_lot_expiry'
        verbose_name = 'Caducidad de lote'
        verbose_name_plural = 'Caducidades de lote'

    def __str__(self) -> str:
        return f'expiry({self.lot}): {self.expiration_date}'

    @property
    def product_expiry_alert(self) -> bool:
        """La caducidad ya se alcanzó (Odoo ``_compute_product_expiry_alert``)."""
        if not self.expiration_date:
            return False
        return self.expiration_date <= timezone.now()
