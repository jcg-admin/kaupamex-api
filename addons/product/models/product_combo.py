"""``product.combo`` — una *elección* dentro de un producto combo.

Adaptación de ``odoo19c: addons/product/models/product_combo.py``
(``odoo-tools@622ddc2aa5``, licencia ``LGPL-3`` declarada en
``addons/product/__manifest__.py``).

Un **producto** de tipo ``combo`` es el menú; un ``product.combo`` es una
elección dentro de ese menú (*"Combo Choices"*), y un ``product.combo.item``
es una opción concreta dentro de la elección. La relación menú→elección es
muchos a muchos y la declara ``product.template.combo_ids``, como en la
fuente.

``base_price`` es el **mínimo** precio entre las opciones, convertido a la
moneda de la elección: así se prorratea el precio del menú entre sus
elecciones sin que la opción que el cliente elija cambie el total.

Las restricciones corren en ``create`` y ``write`` del ORM, con las opciones
ya escritas, igual que en la fuente.
"""

import api
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.timestamped_mixin import (TimeStampedModel,
                                                  record_transaction_now)
from exceptions import ValidationError
from tools.translate import _


class ProductCombo(models.BaseModel, TimeStampedModel):
    """``product.combo`` — una elección dentro de un producto combo."""

    _name = 'product.combo'
    _description = "Product Combo"
    _order = 'sequence, id'

    name = fields.Char(string="Name", required=True, max_length=255)
    sequence = fields.Integer(default=10, copy=False)
    company_id = fields.Many2one(
        ResCompany,
        string="Company",
        db_column='company_id',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        index=True,
        related_name='combo_ids',
    )
    combo_item_count = fields.Integer(
        string="Product Count", compute='_compute_combo_item_count',
        store=False,
    )
    currency_id = fields.Many2one(
        'base.ResCurrency', compute='_compute_currency_id', store=False,
        related_name='+',
    )
    #: ``Monetary`` y no ``Float``: es el mínimo de ``lst_price``, que aquí
    #: ya es ``Monetary``.
    base_price = fields.Monetary(
        string="Combo Price",
        help="The minimum price among the products in this combo. This value"
             " will be used to prorate the price of this combo with respect"
             " to the other combos in a combo product. This heuristic ensures"
             " that whatever product the user chooses in a combo, it will"
             " always be the same price.",
        compute='_compute_base_price',
        store=False,
    )

    class Meta:
        db_table = 'product_combo'
        ordering = ['sequence', 'id']
        verbose_name = 'Elección de combo'
        verbose_name_plural = 'Elecciones de combo'

    def __str__(self):
        return self.name

    @api.depends('combo_item_ids')
    def _compute_combo_item_count(self):
        # Initialize combo_item_count to 0 as _read_group won't return any
        # results for new combos.
        self.combo_item_count = 0
        # Optimization to count the number of combo items in each combo.
        for combo, item_count in self.env['product.combo.item']._read_group(
            domain=[('combo_id', 'in', self.ids)],
            groupby=['combo_id'],
            aggregates=['__count'],
        ):
            combo.combo_item_count = item_count

    @api.depends('company_id')
    def _compute_currency_id(self):
        main_company = ResCompany.get_main_company()
        main_currency = main_company.currency if main_company else None
        for combo in self:
            company = combo.company_id
            combo.currency_id = (
                (company.currency if company else None) or main_currency
            )

    @api.depends('combo_item_ids')
    def _compute_base_price(self):
        for combo in self:
            combo.base_price = min(combo.combo_item_ids.mapped(
                lambda item: item.currency_id._convert(
                    from_amount=item.lst_price,
                    to_currency=combo.currency_id,
                    company=combo.company_id or self.env.company,
                    date=record_transaction_now(combo),
                )
            )) if combo.combo_item_ids else 0

    @api.constrains('combo_item_ids')
    def _check_combo_item_ids_not_empty(self):
        if any(not combo.combo_item_ids for combo in self):
            raise ValidationError(
                _("A combo choice must contain at least 1 product."))

    @api.constrains('combo_item_ids')
    def _check_combo_item_ids_no_duplicates(self):
        for combo in self:
            if (len(combo.combo_item_ids.mapped('product_id'))
                    < len(combo.combo_item_ids)):
                raise ValidationError(
                    _("A combo choice can't contain duplicate products."))

    @api.constrains('company_id')
    def _check_company_id(self):
        templates = self.env['product.template'].sudo().search(
            [('combo_ids', 'in', self.ids)])
        templates._check_company(fnames=['combo_ids'])
        self.combo_item_ids._check_company(fnames=['product_id'])
