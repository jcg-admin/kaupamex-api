"""``product.combo.item`` — una **opción concreta** dentro de una elección.

Adaptación de ``odoo19c: addons/product/models/product_combo_item.py``
(``odoo-tools@622ddc2aa5``, licencia ``LGPL-3`` declarada en
``addons/product/__manifest__.py``).

``extra_price`` es ``Monetary`` y no ``Float``: la línea de venta lo suma a un
precio que aquí ya es ``Monetary``.
"""

import decimal

import api
import fields
import models

from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import ValidationError
from tools.translate import _


class ProductComboItem(models.BaseModel, TimeStampedModel):
    """``product.combo.item`` — una opción ofrecida dentro de una elección."""

    _name = 'product.combo.item'
    _description = "Product Combo Item"
    _check_company_auto = True

    company_id = fields.Many2one(
        'base.ResCompany',
        related='combo_id.company_id', precompute=True, store=True,
        db_column='company_id',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='combo_item_ids',
    )
    combo_id = fields.Many2one(
        'product.ProductCombo',
        db_column='combo_id',
        on_delete=models.CASCADE,
        null=False,
        index=True,
        related_name='combo_item_ids',
    )
    product_id = fields.Many2one(
        'product.ProductProduct',
        string="Options",
        db_column='product_id',
        on_delete=models.PROTECT,
        domain=[('type', '!=', 'combo')],
        null=False,
        check_company=True,
        related_name='combo_item_ids',
    )
    currency_id = fields.Many2one(
        'base.ResCurrency', related='product_id.currency_id', store=False,
        related_name='+',
    )
    lst_price = fields.Monetary(
        string="Original Price", related='product_id.lst_price',
        store=False,
    )
    extra_price = fields.Monetary(
        string="Extra Price",
        max_digits=16,
        decimal_places=2,
        default=decimal.Decimal('0.00'),
    )

    class Meta:
        db_table = 'product_combo_item'
        ordering = ['combo_id_id', 'id']
        verbose_name = 'Opción de combo'
        verbose_name_plural = 'Opciones de combo'

    def __str__(self):
        return f'{self.combo_id} / {self.product_id}'

    @api.constrains('product_id')
    def _check_product_id_no_combo(self):
        if any(combo_item.product_id.type == 'combo'
               for combo_item in self):
            raise ValidationError(
                _("A combo choice can't contain products of type \"combo\"."))
