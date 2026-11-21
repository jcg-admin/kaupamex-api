"""``product.supplierinfo`` — el precio de un proveedor para un producto.

Adaptación de ``addons/product/models/product_supplierinfo.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 119 líneas). Una fila responde: *"a
qué precio, en qué unidad, desde qué cantidad y con cuánto plazo me vende
**este** proveedor **este** producto"*. Es la tarifa de compra, la contraparte
de ``product.pricelist`` (que es la de venta).

Plantilla **y** variante, y por qué las dos
===========================================

La fila apunta a la **plantilla** (obligatorio) y opcionalmente a una
**variante**. No es redundancia: es el alcance del precio.

- Sólo plantilla → el precio vale para **todas** las variantes. Es el caso
  normal: el proveedor cotiza "camiseta", no "camiseta roja talla M".
- Plantilla + variante → el precio vale **sólo** para esa combinación. El
  ``help`` de la referencia lo dice al revés de como se lee al principio:
  *"If not set, the vendor price will apply to all variants"*.

La consecuencia es que **la variante manda sobre la plantilla** cuando ambas
encajan, y eso se ve en ``code_for`` más abajo: el bucle sigue buscando hasta
encontrar la entrada específica de la variante, y sólo entonces corta.

El orden es el que decide qué fila gana
=======================================

``_order = 'sequence, min_qty DESC, price, id'``. Leído en orden: el proveedor
con menos ``sequence`` primero; a igual secuencia, **la cantidad mínima mayor
primero** —porque comprar 100 sale más barato que comprar 10 y el escalón alto
debe evaluarse antes—; a igual cantidad, el precio menor. Invertir el
``DESC`` daría siempre el escalón de 1 unidad y el descuento por volumen no se
aplicaría nunca.

Divergencia declarada: ``price`` y ``discount`` son ``Monetary``
================================================================

La referencia declara los dos como ``Float``. Aquí son ``fields.Monetary``
—``DecimalField``— por el criterio de **comparabilidad** que H-API-168 fijó,
no por gusto:

1. Esta fila alimenta la línea de compra. ``purchase_order_line.price_unit``
   y ``purchase_order_line.discount`` ya son ``Monetary`` en este árbol
   (``purchase/models/purchase_order_line.py:38`` y ``:41``, medido) — con
   ``max_digits=5, decimal_places=2`` en el descuento, que es lo que se copia
   aquí. Un precio de proveedor en ``float`` al lado de la línea que lo
   consume redondearía distinto el mismo importe según por dónde se leyera.
2. ``price_discounted`` convierte ``price`` con ``Uom._compute_price``, que
   conserva el tipo del importe: el dinero no sale de ``Decimal``.

``variant_seller_ids`` no es de variantes
=========================================

La plantilla declara ``seller_ids`` y ``variant_seller_ids``
(``product_template.py:126-127``) y **las dos** usan el mismo inverso
``product_tmpl_id``; sólo difieren en el ``depends_context=('company',)`` de
la primera. En Django una FK da exactamente **un** ``related_name``, así que
se declara ``seller_ids`` y ``variant_seller_ids`` queda como alias explícito
sobre el mismo conjunto.
"""

import api
import fields
import models

from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from addons.base.models.res_partner import ResPartner
from addons.base.models.timestamped_mixin import TimeStampedModel
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_template import ProductTemplate
from addons.uom.models.uom_uom import Uom
from orm.environments import env
from tools.translate import _


def _default_company():
    """≙ ``default=lambda self: self.env.company.id``
    (``odoo19c: product_supplierinfo.py:33-35``)."""
    company = env().company
    return company.pk if company is not None else None


def _default_currency():
    """≙ ``default=lambda self: self.env.company.currency_id.id``
    (``odoo19c: product_supplierinfo.py:36-39``): la moneda de la empresa
    activa, o ninguna si no hay empresa en contexto."""
    company = env().company
    return company.currency_id if company is not None else None


class ProductSupplierinfo(models.BaseModel, TimeStampedModel):
    """``product.supplierinfo`` — la tarifa de un proveedor."""

    _name = 'product.supplierinfo'
    _description = "Supplier Pricelist"
    _order = 'sequence, min_qty DESC, price, id'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        ResPartner, string='Vendor',
        null=False, on_delete=models.CASCADE,
        check_company=True,
        db_index=True,
        related_name='supplierinfo_ids',
        db_column='partner_id',
    )
    product_name = fields.Char(
        'Vendor Product Name',
        max_length=255, blank=True, default='',
        help="This vendor's product name will be used when printing a "
             "request for quotation. Keep empty to use the internal one.",
    )
    product_code = fields.Char(
        'Vendor Product Code',
        max_length=64, blank=True, default='',
        help="This vendor's product code will be used when printing a "
             "request for quotation. Keep empty to use the internal one.",
    )
    sequence = fields.Integer(
        'Sequence', default=1,
        help="Assigns the priority to the list of product vendor.",
    )
    product_uom_id = fields.Many2one(
        Uom, string='Unit',
        compute='_compute_product_uom_id', store=True, readonly=False,
        precompute=True,
        db_column='product_uom_id',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='supplierinfo_ids',
    )
    min_qty = fields.Float(
        'Quantity', default=0.0,
        help="The quantity to purchase from this vendor to benefit from the "
             "unit price. If a vendor unit is set, quantity should be "
             "specified in this unit, otherwise it should be specified in "
             "the default unit of the product.",
    )
    #: ``Monetary`` y no ``Float``: ver el docstring del módulo.
    price = fields.Monetary(
        'Unit Price', max_digits=16, decimal_places=2, default=0,
        help="The price to purchase a product",
    )
    price_discounted = fields.Monetary(
        'Discounted Price', compute='_compute_price_discounted',
        store=False,
    )
    company_id = fields.Many2one(
        ResCompany, string='Company',
        default=_default_company,
        db_column='company_id',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='supplierinfo_ids',
    )
    currency_id = fields.Many2one(
        ResCurrency, string='Currency',
        default=_default_currency,
        db_column='currency_id',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='supplierinfo_ids',
    )
    date_start = fields.Date(
        'Start Date', null=True, blank=True,
        help="Start date for this vendor price",
    )
    date_end = fields.Date(
        'End Date', null=True, blank=True,
        help="End date for this vendor price",
    )
    product_id = fields.Many2one(
        ProductProduct, string='Product Variant', check_company=True,
        domain="[('product_tmpl_id', '=', product_tmpl_id)] "
               "if product_tmpl_id else []",
        compute='_compute_product_id', store=True, readonly=False,
        precompute=True,
        db_column='product_id',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        db_index=True,
        related_name='supplierinfo_ids',
        help="If not set, the vendor price will apply to all variants of "
             "this product.",
    )
    product_tmpl_id = fields.Many2one(
        ProductTemplate, string='Product Template', check_company=True,
        compute='_compute_product_tmpl_id', precompute=True,
        store=True, readonly=False,
        db_column='product_tmpl_id',
        null=False, on_delete=models.CASCADE,
        db_index=True,
        related_name='seller_ids',
    )
    product_variant_count = fields.Integer(
        'Variant Count', related='product_tmpl_id.product_variant_count',
    )
    delay = fields.Integer(
        'Lead Time', default=1,
        help="Lead time in days between the confirmation of the purchase "
             "order and the receipt of the products in your warehouse. Used "
             "by the scheduler for automatic computation of the purchase "
             "order planning.",
    )
    #: ``Monetary`` y no ``Float``: ver el docstring del módulo.
    discount = fields.Monetary(
        string="Discount (%)", max_digits=5, decimal_places=2, default=0,
    )

    class Meta:
        db_table = 'product_supplierinfo'
        # ``_order = 'sequence, min_qty DESC, price, id'``.
        ordering = ['sequence', '-min_qty', 'price', 'id']
        verbose_name = 'Tarifa de proveedor'
        verbose_name_plural = 'Tarifas de proveedor'

    def __str__(self):
        return str(self.partner_id)

    @api.depends('product_id', 'product_tmpl_id')
    def _compute_product_uom_id(self):
        for rec in self:
            if not rec.product_uom_id:
                rec.product_uom_id = (rec.product_id.uom_id if rec.product_id
                                      else rec.product_tmpl_id.uom_id)

    @api.depends('product_id', 'product_tmpl_id')
    def _compute_price(self):
        for rec in self:
            rec.price = (rec.product_id.standard_price if rec.product_id
                         else rec.product_tmpl_id.standard_price
                         if rec.product_tmpl_id else 0.0)

    @api.depends('discount', 'price')
    def _compute_price_discounted(self):
        for rec in self:
            product_uom = (rec.product_id or rec.product_tmpl_id).uom_id
            rec.price_discounted = rec.product_uom_id._compute_price(
                rec.price, product_uom) * (1 - rec.discount / 100)

    @api.depends('product_id')
    def _compute_product_tmpl_id(self):
        for rec in self:
            if rec.product_id:
                rec.product_tmpl_id = rec.product_id.product_tmpl_id

    @api.depends('product_id', 'product_tmpl_id', 'product_variant_count')
    def _compute_product_id(self):
        for rec in self:
            if self.env.get('default_product_id'):
                rec.product_id = self.env.get('default_product_id')

    @api.onchange('product_tmpl_id')
    def _onchange_product_tmpl_id(self):
        """Clear product variant if it no longer matches the product
        template."""
        if (self.product_id and self.product_id
                not in self.product_tmpl_id.product_variant_ids):
            self.product_id = False

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Vendor Pricelists'),
            'template': '/product/static/xls/product_supplierinfo.xls'
        }]

    def _sanitize_vals(self, vals):
        """Sanitize vals to sync product variant & template on read/write."""
        # add product's product_tmpl_id if none present in vals
        if vals.get('product_id') and not vals.get('product_tmpl_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            vals['product_tmpl_id'] = product.product_tmpl_id.id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sanitize_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._sanitize_vals(vals)
        return super().write(vals)

    def _get_filtered_supplier(self, company_id, product_id, params=False):
        # ``res.partner`` es aquí un modelo de Django: la fila ya está leída
        # y no hay ``sudo()`` que aplicar para leer ``active``. Sin empresa
        # activa sólo pasan las tarifas de todas las empresas.
        company = company_id.id if company_id else False
        return self.filtered(
            lambda s: (not s.company_id or s.company_id.id == company)
            and (s.partner_id.active
                 and (not s.product_id or s.product_id == product_id)))
