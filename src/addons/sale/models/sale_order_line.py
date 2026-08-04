"""Modelo ``SaleOrderLine`` — addon ``sale``.

Adaptación fiel de Odoo ``sale.order.line`` (``sale/models/sale_order_line.py``):
``product_id``/``product_uom_qty``/``price_unit``/``discount`` +
``price_subtotal``/``price_tax``/``price_total`` computados y **redondeados por
línea** (``_compute_amount``, sale_order_line.py:852). Precios IVA-incluido (MX):
el total de línea es ``price_unit*qty*(1-discount/100)`` y el IVA se extrae con la
tasa vigente, cuantizando por línea (equivale a ``_round_base_lines_tax_details``).
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
import fields
import models

from addons.base.models import TimeStampedModel
from addons.base_setup.settings_access import get_setting
from addons.stock.services import InventoryService


class SaleOrderLine(TimeStampedModel):
    """``sale.order.line`` — una línea de la orden/carrito."""

    order           = fields.Many2one(
        'sale.SaleOrder', on_delete=models.CASCADE, related_name='order_line',
        help_text='Odoo order_id.',
    )
    product         = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT,
        related_name='sale_order_lines', help_text='Odoo product_id.',
    )
    name            = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Descripción de la línea (Odoo name).',
    )
    product_uom_qty = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Cantidad (Odoo product_uom_qty).',
    )
    price_unit      = fields.Monetary(
        max_digits=12, decimal_places=2, help_text='Odoo price_unit (IVA incl.).',
    )
    discount        = fields.Monetary(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Descuento % de la línea (Odoo discount).',
    )
    # ------------------------------------------------------------------
    # E1-bis — marcadores de línea NO-producto (H-API-24 / H-API-30).
    #
    # Los importes que no son de producto (envío, descuento de cupón) hoy son
    # escalares que nunca llegan a ``order_line``, así que ``amount_total``
    # los excluye por construcción. La forma fiel los materializa como líneas
    # y los marca para poder distinguirlas:
    #
    # - ``is_delivery`` ≙ Odoo ``delivery/models/sale_order_line.py:9``.
    # - ``is_reward``   ≙ la línea de recompensa de ``sale_loyalty`` (precio
    #   negativo).
    #
    # Ambos marcadores nacen juntos por decisión del ejecutor (2026-07-28):
    # envío y descuento comparten mecanismo en el monolito modular, y comparten
    # la misma causa raíz. Son marcadores, NO un tipo de línea: la línea sigue
    # siendo una ``sale.order.line`` normal y entra a los totales como
    # cualquier otra.
    # ------------------------------------------------------------------
    is_delivery     = fields.Boolean(
        default=False, db_index=True,
        help_text='La línea representa el costo de envío (Odoo is_delivery).',
    )
    is_reward       = fields.Boolean(
        default=False, db_index=True,
        help_text='La línea representa un descuento/recompensa (precio negativo).',
    )

    class Meta:
        db_table     = 'sale_order_line'
        verbose_name = 'Línea de orden de venta'

    def __str__(self):
        return f'{self.name or self.product_id} ×{self.product_uom_qty}'

    # ------------------------------------------------------------------
    # Disparo del recálculo de la orden (H-API-30) — equivalente Django del
    # ``@api.depends('order_line.price_subtotal', ...)`` que Odoo declara en
    # ``SaleOrder.amount_untaxed/tax/total`` (sale/models/sale_order.py:232-234).
    # En la referencia el motor de dependencias de Odoo dispara
    # ``_compute_amounts`` sólo cuando cambia un campo del que depende; Django
    # no tiene ese motor, así que aquí se dispara en **cada** ``save()``/
    # ``delete()`` de la línea, sin distinguir qué campo cambió. El costo es
    # un recompute redundante ocasional (p. ej. renombrar la línea sin tocar
    # precio/cantidad) — no hay recursión: ``_compute_amounts`` guarda la
    # ORDEN (``SaleOrder.save``, sin overridear), nunca vuelve a tocar la línea.
    #
    # **Alcance del disparo — sólo mutaciones a nivel instancia.** Un
    # ``QuerySet.filter(...).delete()`` (o ``.update()``) no pasa por aquí:
    # Django hace DELETE/UPDATE en bloque sin invocar el ``delete()``/``save()``
    # de cada fila. Los llamadores que borran líneas en bloque
    # (``delivery.set_delivery_line``, ``sale_loyalty.set_reward_line``,
    # ``sale_product_matrix.SaleOrderMatrix.apply``, ``sale.services.
    # clear_draft_items``) llaman a ``order._compute_amounts()`` explícitamente
    # tras el borrado en bloque — ver el docstring de cada uno.
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.order._compute_amounts()

    def delete(self, *args, **kwargs):
        order = self.order
        result = super().delete(*args, **kwargs)
        order._compute_amounts()
        return result

    # Desglose por línea — de sale.order.line._compute_amount (sale_order_line.py:852).
    def price_total(self) -> Decimal:
        gross = (self.price_unit * self.product_uom_qty
                 * (Decimal('1') - self.discount / Decimal('100')))
        return gross.quantize(Decimal('0.01'))

    def price_tax(self) -> Decimal:
        rate = get_setting('iva_rate')
        return (self.price_total() * rate / (1 + rate)).quantize(Decimal('0.01'))

    def price_subtotal(self) -> Decimal:
        return self.price_total() - self.price_tax()

    # ------------------------------------------------------------------
    # V2 unificación orders→sale: la línea del draft (carrito) necesita el
    # estado VIVO del catálogo. En Odoo ``website_sale`` recalcula el precio
    # del carrito contra la pricelist vigente; aquí el vigente es
    # ``ProductProduct.lst_price`` — el de la ficha más el extra de los
    # valores de atributo de la variante (odoo19c:
    # ``product/models/product_product.py``).
    #
    # El eje ``variant`` desapareció: ``product`` **es** la variante
    # (H-API-213). La existencia se deriva de ``stock.quant`` vía
    # ``InventoryService``, no de una columna del producto (odoo19c:
    # ``stock/models/stock_quant.py:119-122``).
    # ------------------------------------------------------------------
    def current_price(self) -> Decimal:
        """Precio vigente del catálogo (Odoo ``lst_price``)."""
        return self.product.lst_price

    def is_available(self) -> bool:
        """Paridad con la guardia histórica de carrito (H-CICLO42-01)."""
        if not self.product.active:
            return False
        return self.available_stock() >= self.product_uom_qty

    def available_stock(self) -> Decimal:
        return InventoryService.available_quantity(self.product)
