"""Dirección de entrega de la venta — ``delivery.DeliveryAddress``.

Vivía en ``orders.OrderAddress``. Su redomiciliación la dicta la referencia,
no una preferencia: en Odoo la dirección de envío **no es del eje comercial**
— ``sale.order`` sólo *apunta* con ``partner_shipping_id`` a un
``res.partner``, y el dato vive fuera. Ver
``analisis-estructura-destino-comercial.rst`` (tabla 5, fila
``orders.OrderAddress``): *"Pertenece al dominio contact/delivery, no a
orders/sale"*. De los dos candidatos, ``contact`` en este monolito no tiene
capa de modelos (es el addon del formulario de contacto), así que el hogar es
``delivery`` — el dominio de fulfillment, que es quien consume la dirección.

**Divergencia declarada:** aquí se conserva un **snapshot inmutable**
(BR-005) en vez de la FK a ``res.partner`` de la referencia, porque el
requisito es que la dirección de entrega no cambie si el comprador edita su
libreta después de comprar. Odoo no lo garantiza con la FK sola. La
divergencia es deliberada; converger exigiría versionar el contacto.

La FK al espejo desapareció con el addon ``orders``: sólo queda ``sale_order``,
ahora obligatoria.
"""
from django.db import models

from addons.base.models import TimeStampedModel


class DeliveryAddress(TimeStampedModel):
    """Snapshot de la dirección de envío al momento del checkout. BR-005."""

    sale_order     = models.OneToOneField(
        'sale.SaleOrder', on_delete=models.CASCADE,
        related_name='delivery_address',
    )
    recipient_name = models.CharField(max_length=200)
    street         = models.CharField(max_length=255)
    city           = models.CharField(max_length=100)
    state          = models.CharField(max_length=100)
    zip_code       = models.CharField(max_length=10)
    country        = models.CharField(max_length=2, default='MX')
    phone          = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        db_table     = 'delivery_address'
        verbose_name = 'Dirección de entrega'

    def __str__(self):
        return f'{self.recipient_name} — {self.city}'
