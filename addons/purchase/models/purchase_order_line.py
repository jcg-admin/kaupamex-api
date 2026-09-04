"""Modelo ``PurchaseOrderLine`` — addon ``purchase``.

Adaptación fiel de Odoo ``purchase.order.line`` (``purchase/models/
purchase_order_line.py``, idéntico en 18 y 19): línea de una orden de compra.
Núcleo verificado en ambas versiones — ``name``/``product_qty``/``price_unit``/
``discount``/``product_id``/``order_id`` + ``price_subtotal`` computado. Espeja el
desglose por línea de ``sale.order.line`` (IVA-incluido MX) para consistencia.

``company_id``/``currency_id`` (tarea #266) — dependencias de ``price_total_cc``
====================================================================================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Símbolo de la referencia
     - Forma aquí
   * - ``company_id`` (``odoo19c: purchase_order_line.py:53``)
     - campo homónimo, **stored**. La fuente lo declara
       ``related='order_id.company_id', store=True, readonly=True``; este
       ORM no dispara el ``related=`` con columna (``src/orm/models.py:
       1495-1511`` sólo traversa el que **no** tiene ``store``), así que se
       sincroniza en ``save()`` — mismo patrón que
       ``AccountReconcileModelLine.company``/``_sync_company``
       (``api: addons/account/models/account_reconcile_model.py:218-221,
       273-276``).
   * - ``currency_id`` (``odoo19c: purchase_order_line.py:85``)
     - ``@property`` — la fuente lo declara
       ``related='order_id.currency_id'`` **sin** ``store``, así que aquí no
       hay columna que sincronizar; se navega el FK directo, mismo patrón
       que ``PurchaseRequisitionLine.company``
       (``api: addons/purchase_requisition/models/purchase_requisition.py:
       514-517``).
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
import fields
import models

from addons.base_setup.settings_access import get_setting
from addons.base.models import TimeStampedModel


class PurchaseOrderLine(TimeStampedModel):
    """``purchase.order.line`` — una línea de la orden de compra."""

    order_id    = fields.Many2one(
        'purchase.PurchaseOrder', on_delete=models.CASCADE, related_name='order_line',
        help_text='Odoo order_id.',
        db_column='order_id',
    )
    product_id  = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT,
        related_name='purchase_order_lines', help_text='Odoo product_id.',
        db_column='product_id',
    )
    name        = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Descripción de la línea (Odoo purchase.order.line.name).',
    )
    product_qty = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Cantidad (Odoo product_qty).',
    )
    price_unit  = fields.Monetary(
        max_digits=12, decimal_places=2, help_text='Odoo price_unit (IVA incl.).',
    )
    discount    = fields.Monetary(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Descuento % de la línea (Odoo discount).',
    )
    # Odoo purchase.order.line.company_id — ver docstring del módulo (tarea #266).
    company_id = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='+', db_column='company_id',
        help_text='Odoo company_id (related="order_id.company_id", '
                  'store=True, readonly=True) — columna sincronizada en '
                  'save(), ver docstring del módulo.',
    )

    class Meta:
        db_table = 'purchase_order_line'
        verbose_name = 'Línea de orden de compra'
        verbose_name_plural = 'Líneas de orden de compra'

    def __str__(self) -> str:
        return f'{self.name or self.product_id} ×{self.product_qty}'

    @property
    def currency_id(self):
        """≙ ``currency_id`` (``related='order_id.currency_id'``, sin
        ``store``) — ver docstring del módulo."""
        return self.order_id.currency_id if self.order_id_id else None

    def _sync_company(self):
        """Sincroniza ``company_id`` con el de la orden — divergencia
        declarada en el docstring del módulo (``related=…, store=True`` sin
        motor de recompute)."""
        self.company_id = self.order_id.company_id if self.order_id_id else None

    def save(self, *args, **kwargs):
        """Sincroniza ``company_id`` antes de persistir — ver
        ``_sync_company``."""
        self._sync_company()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'company_id' not in update_fields:
            kwargs['update_fields'] = [*update_fields, 'company_id']
        return super().save(*args, **kwargs)

    # Desglose por línea — espeja sale.order.line (Odoo _compute_amount).
    def price_total(self) -> Decimal:
        gross = (self.price_unit * self.product_qty
                 * (Decimal('1') - self.discount / Decimal('100')))
        return gross.quantize(Decimal('0.01'))

    def price_tax(self) -> Decimal:
        rate = get_setting('iva_rate')
        return (self.price_total() * rate / (1 + rate)).quantize(Decimal('0.01'))

    def price_subtotal(self) -> Decimal:
        return self.price_total() - self.price_tax()
