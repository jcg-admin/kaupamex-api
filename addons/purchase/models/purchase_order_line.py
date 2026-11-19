"""Modelo ``PurchaseOrderLine`` — addon ``purchase``.

Adaptación fiel de Odoo ``purchase.order.line`` (``purchase/models/
purchase_order_line.py``, idéntico en 18 y 19): línea de una orden de compra.
Núcleo verificado en ambas versiones — ``name``/``product_qty``/
``price_unit``/``discount``/``product_id``/``order_id``, ``tax_ids`` y los
importes almacenados que ``_compute_amount`` calcula con el motor de
``account.tax`` (``odoo19c: :106-136``). El resto del porte de la clase está
descompuesto en unidades: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/purchase-order-line-port.md``.

``company_id``/``currency_id`` (tarea #266), dependencias de ``price_total_cc``
===============================================================================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Símbolo de la referencia
     - Forma aquí
   * - ``company_id`` (``odoo19c: purchase_order_line.py:53``)
     - ``related='order_id.company_id', store=True, readonly=True``, como en
       la fuente. Se sincronizaba en ``save()`` por una razón que ya no era
       cierta («este ORM no dispara el ``related=`` con columna»): el mismo
       modelo declara ``partner_id`` así. Diseño
       ``designs/new-line-recompute-flow.md``.
   * - ``currency_id`` (``odoo19c: purchase_order_line.py:85``)
     - ``@property`` — la fuente lo declara
       ``related='order_id.currency_id'`` **sin** ``store``, así que aquí no
       hay columna que sincronizar; se navega el FK directo, mismo patrón
       que ``PurchaseRequisitionLine.company``
       (``api: addons/purchase_requisition/models/purchase_requisition.py:
       514-517``).
"""
from collections import defaultdict
from contextlib import nullcontext
from datetime import datetime, time
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from pytz import UTC

from django.apps import apps
from markupsafe import escape
from django.db import models as dj_models
import api
import fields
import models
from django.utils import timezone

from addons.account.models.account_fiscal_position import (
    AccountFiscalPosition)
from addons.analytic.models.analytic_mixin import AnalyticMixin
from addons.base.models import TimeStampedModel
from addons.mail.models.mail_thread import register_source_body
from orm.environments import company_scope, context_scope, env
from tools.misc import get_lang
from tools.translate import _


@register_source_body('purchase.track_po_line_qty_received_template')
def _track_po_line_qty_received_body(record, values):
    """El cuerpo de ``purchase.track_po_line_qty_received_template``.

    ≙ ``odoo19c: addons/purchase/data/mail_templates.xml:18-26``, compuesto en
    Python porque QWeb no se porta (DEC-EM-01, DEC-AF-08). ``t-esc`` escapa,
    y aquí ``escape`` hace lo mismo; las cantidades salen como ``float``,
    que es lo que la vista escribe (``float(qty_received)`` y el ``Float`` de
    ``line.qty_received`` en la fuente).
    """
    line = values['line']
    return (
        '<div><strong>%s</strong><ul><li>%s:</li>%s %s -&gt; %s<br/></ul>'
        '</div>' % (
            escape(_('The received quantity has been updated.')),
            escape(line.product_id.display_name),
            escape(_('Received Quantity:')),
            escape(str(float(line.qty_received or 0))),
            escape(str(float(values['qty_received']))),
        ))


class PurchaseOrderLine(models.BaseModel, AnalyticMixin, TimeStampedModel):
    """``purchase.order.line`` — una línea de la orden de compra.

    ``_inherit = ['analytic.mixin']`` (``odoo19c: :15``) por herencia.
    """

    _name = 'purchase.order.line'
    _description = 'Purchase Order Line'
    _order = 'order_id, sequence, id'

    #: ≙ ``sequence`` (``odoo19c: :22``).
    sequence = fields.Integer(string='Sequence', default=10)
    #: ≙ ``partner_id`` (``odoo19c: :84``): el proveedor de la orden,
    #: almacenado para filtrar líneas por proveedor.
    partner_id = fields.Many2one(
        'base.ResPartner', verbose_name='Partner',
        related='order_id.partner_id',
        store=True, readonly=True, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='purchase_line_ids',
        db_column='partner_id',
    )

    order_id = fields.Many2one(
        'purchase.PurchaseOrder', null=False, on_delete=models.CASCADE,
        related_name='order_line',
        help_text='Odoo order_id.',
        db_column='order_id',
    )
    product_id = fields.Many2one(
        'product.ProductProduct', on_delete=models.PROTECT, null=True,
        blank=True,
        related_name='purchase_order_lines', help_text='Odoo product_id.',
        db_column='product_id',
    )
    #: ≙ ``name`` (``odoo19c: :19-20``): ``Text`` calculado almacenado y
    #: editable, como ``price_unit`` y ``discount``.
    name = fields.Text(
        'Description', blank=True,
        compute='_compute_price_unit_and_date_planned_and_name', store=True,
        readonly=False,
        help_text='Descripción de la línea (Odoo purchase.order.line.name).',
    )
    #: ≙ ``display_type`` (``odoo19c: purchase_order_line.py:91-94``).
    display_type = fields.Selection(
        [('line_section', 'Section'), ('line_subsection', 'Subsection'),
         ('line_note', 'Note')],
        max_length=16, null=True, blank=True,
        help_text='Technical field for UX purpose.')
    #: ≙ ``is_downpayment`` (``odoo19c: purchase_order_line.py:95``).
    is_downpayment = fields.Boolean(default=False)
    #: ≙ ``product_uom_id`` (``odoo19c: purchase_order_line.py:36``,
    #: ``ondelete='restrict'``). La fuente lo fija en el onchange del
    #: producto (``:386``).
    product_uom_id = fields.Many2one(
        'uom.Uom', verbose_name='Unit', null=True, blank=True,
        on_delete=dj_models.PROTECT, related_name='+',
        db_column='product_uom_id')
    #: ≙ ``selected_seller_id`` (``purchase_order_line.py:96``): la tarifa del
    #: proveedor que aplica a la línea, calculada y sin columna.
    selected_seller_id = fields.Many2one(
        'product.ProductSupplierinfo', store=False,
        compute='_compute_selected_seller_id',
        on_delete=dj_models.SET_NULL, related_name='+')
    #: ≙ ``product_qty`` (``odoo19c: :23``): ``Float(digits='Product Unit',
    #: required=True)``, sin valor por defecto. Se declara como ``quantity``
    #: de ``account.move.line`` (``Decimal``, cuatro decimales): mismo
    #: ``digits``, mismo mecanismo de pila.
    product_qty = fields.Monetary(
        'Quantity', max_digits=16, decimal_places=4,
        help_text='Odoo product_qty (digits="Product Unit", required).',
    )
    #: ≙ ``product_uom_qty`` (``odoo19c: purchase_order_line.py:24``): la
    #: cantidad en la unidad del producto. La suma
    #: ``ProductProduct._compute_purchased_product_qty`` (``product.py:75``).
    product_uom_qty = fields.Float(
        'Total Quantity', compute='_compute_product_uom_qty', store=True,
        null=True, blank=True)
    price_unit = fields.Monetary(
        max_digits=12, decimal_places=2,
        compute='_compute_price_unit_and_date_planned_and_name', store=True,
        readonly=False,
        help_text='Odoo price_unit (IVA incl.).',
    )
    discount = fields.Monetary(
        max_digits=5, decimal_places=2, null=True, blank=True,
        compute='_compute_price_unit_and_date_planned_and_name', store=True,
        readonly=False,
        help_text='Descuento % de la línea (Odoo discount).',
    )
    #: ≙ ``tax_ids`` (``odoo19c: :34``), con la tabla que la fuente deriva
    #: (``'%s_%s_rel' % tuple(sorted(tablas))``,
    #: ``fields_relational.py:1291``).
    tax_ids = fields.Many2many(
        'account.AccountTax', string='Taxes',
        relation='account_tax_purchase_order_line_rel',
        column1='purchase_order_line_id', column2='account_tax_id',
        related_name='+', blank=True,
        context={'active_test': False, 'hide_original_tax_ids': True})
    #: ≙ ``price_subtotal``/``price_total``/``price_tax`` (``odoo19c:
    #: :46-48``), almacenados y calculados por ``_compute_amount``.
    #: ``price_tax`` es ``Float`` en la fuente y aquí ``Monetary``: el motor de
    #: ``account.tax`` y los importes son ``Decimal`` (la misma divergencia de
    #: pila que ``sale.order.line``).
    price_subtotal = fields.Monetary(
        'Subtotal', max_digits=16, decimal_places=2,
        compute='_compute_amount', store=True, null=True, blank=True)
    price_total = fields.Monetary(
        'Total', max_digits=16, decimal_places=2,
        compute='_compute_amount', store=True, null=True, blank=True)
    price_tax = fields.Monetary(
        'Tax', max_digits=16, decimal_places=2,
        compute='_compute_amount', store=True, null=True, blank=True)
    #: ≙ ``qty_received_method``/``qty_received``/``qty_received_manual``
    #: (``odoo19c: :60-65``). Las cantidades son ``Float(digits='Product
    #: Unit')`` en la fuente y aquí ``Decimal`` de cuatro decimales, como
    #: ``product_qty``. ``purchase_stock`` añade el método ``stock_moves``.
    qty_received_method = fields.Selection(
        [('manual', 'Manual')], string='Received Qty Method',
        compute='_compute_qty_received_method', store=True,
        max_length=16, null=True, blank=True,
        help_text='According to product configuration, the received '
                  'quantity can be automatically computed by mechanism:\n'
                  '  - Manual: the quantity is set manually on the line\n'
                  '  - Stock Moves: the quantity comes from confirmed '
                  'pickings\n')
    qty_received = fields.Monetary(
        'Received Qty', max_digits=16, decimal_places=4,
        compute='_compute_qty_received', inverse='_inverse_qty_received',
        compute_sudo=True, store=True, readonly=False,
        null=True, blank=True)
    qty_received_manual = fields.Monetary(
        'Manual Received Qty', max_digits=16, decimal_places=4,
        copy=False, null=True, blank=True)
    #: ≙ ``qty_invoiced``/``qty_to_invoice`` (``odoo19c: :58,66-67``):
    #: ``Float(digits='Product Unit')`` en la fuente, ``Decimal`` de cuatro
    #: decimales aquí, como ``product_qty``. ``invoice_lines`` (``:56``) es el
    #: inverso que ``purchase`` cuelga en ``account.move.line``
    #: (``account_invoice.py``).
    qty_invoiced = fields.Monetary(
        'Billed Qty', max_digits=16, decimal_places=4,
        compute='_compute_qty_invoiced', store=True,
        null=True, blank=True)
    qty_to_invoice = fields.Monetary(
        'To Invoice Quantity', max_digits=16, decimal_places=4,
        compute='_compute_qty_invoiced', store=True, readonly=True,
        null=True, blank=True)
    #: ≙ ``qty_invoiced_at_date``/``amount_to_invoice_at_date``
    #: (``odoo19c: :75-80``): sin columna, dependen de
    #: ``accrual_entry_date``.
    qty_invoiced_at_date = fields.Monetary(
        'Billed', max_digits=16, decimal_places=4,
        compute='_compute_qty_invoiced_at_date')
    amount_to_invoice_at_date = fields.Monetary(
        'Amount', max_digits=16, decimal_places=4,
        compute='_compute_amount_to_invoice_at_date')
    #: ≙ ``qty_received_at_date`` (``odoo19c: :70-74``): sin columna,
    #: depende del contexto ``accrual_entry_date``.
    qty_received_at_date = fields.Monetary(
        'Received', max_digits=16, decimal_places=4,
        compute='_compute_qty_received_at_date')
    #: ≙ los related de la fuente (``odoo19c: :38,54,85-90,105``), sin
    #: columna.
    #: ``product.product`` delega ``type`` en su plantilla con una propiedad,
    #: no con un campo (``product/models/product_product.py:5-40``), así que
    #: la cadena nombra el eslabón de la delegación.
    product_type = fields.Selection(
        related='product_id.product_tmpl.type', readonly=True)
    state = fields.Selection(related='order_id.state', store=False)
    currency_id = fields.Many2one(
        related='order_id.currency_id', string='Currency', related_name='+')
    date_order = fields.Datetime(
        related='order_id.date_order', string='Order Date', readonly=True)
    date_approve = fields.Datetime(
        related='order_id.date_approve', string='Confirmation Date',
        readonly=True)
    tax_calculation_rounding_method = fields.Selection(
        related='company_id.tax_calculation_rounding_method',
        string='Tax calculation rounding method', readonly=True)
    #: ``product.product`` nombra el campo
    #: ``product_template_attribute_values``
    #: (divergencia de nombre del porte de ``product``).
    product_template_attribute_value_ids = fields.Many2many(
        related='product_id.product_template_attribute_values',
        readonly=True, related_name='+')
    #: ≙ ``product_no_variant_attribute_value_ids`` (``odoo19c: :106``), con
    #: la tabla que la fuente deriva.
    product_no_variant_attribute_value_ids = fields.Many2many(
        'product.ProductTemplateAttributeValue',
        string='Product attribute values that do not create variants',
        relation='product_template_attribute_value_purchase_order_line_rel',
        column1='purchase_order_line_id',
        column2='product_template_attribute_value_id',
        related_name='+', blank=True)
    #: ≙ los cómputos sin columna (``odoo19c: :21,35,42-45,107-111``).
    translated_product_name = fields.Text(
        compute='_compute_translated_product_name')
    allowed_uom_ids = fields.Many2many(
        'uom.Uom', compute='_compute_allowed_uom_ids', related_name='+')
    price_unit_product_uom = fields.Float(
        string='Unit Price Product UoM',
        compute='_compute_price_unit_product_uom',
        help="The Price of one unit of the product's Unit of Measure")
    price_unit_discounted = fields.Monetary(
        'Unit Price (Discounted)', compute='_compute_price_unit_discounted')
    parent_id = fields.Many2one(
        'purchase.PurchaseOrderLine', string='Parent Section Line',
        compute='_compute_parent_id', related_name='+')
    #: ≙ ``technical_price_unit`` (``odoo19c: :112``): ``Float`` almacenado;
    #: aquí ``Monetary`` como ``price_unit``.
    technical_price_unit = fields.Monetary(
        max_digits=16, decimal_places=4, null=True, blank=True,
        help='Technical field for price computation')
    #: ≙ ``company_id`` (``odoo19c: :53``): la empresa de la orden,
    #: almacenada. Sin ``ondelete`` en la fuente, o sea ``set null``
    #: (``odoo19c: odoo/orm/fields_relational.py:274-282``).
    company_id = fields.Many2one(
        'base.ResCompany', verbose_name='Company',
        related='order_id.company_id',
        store=True, readonly=True, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', db_column='company_id',
    )

    class Meta:
        db_table = 'purchase_order_line'
        ordering = ['order_id', 'sequence', 'id']
        verbose_name = 'Línea de orden de compra'
        verbose_name_plural = 'Líneas de orden de compra'

    def __str__(self) -> str:
        return f'{self.name or self.product_id} ×{self.product_qty}'

    @api.depends('product_uom_id', 'product_qty', 'product_id.uom_id')
    def _compute_product_uom_qty(self):
        """≙ ``_compute_product_uom_qty`` (``odoo19c: :484-490``)."""
        for line in self:
            # ``product.uom`` es el ``uom_id`` de la fuente: en ``product`` los
            # FK de Django no llevan el sufijo y ``uom_id`` es su ``attname``.
            # Una línea sin unidad copia la cantidad: es la rama
            # ``if not self: return qty`` de ``uom.uom._compute_quantity``
            # (``odoo19c: uom/models/uom_uom.py:162-163``).
            product = line.product_id
            if (product and line.product_uom_id
                    and product.uom != line.product_uom_id):
                # ``product_uom_qty`` es ``Float`` y ``product_qty`` se
                # guarda en ``Decimal`` (ver su declaración).
                line.product_uom_qty = line.product_uom_id._compute_quantity(
                    float(line.product_qty), product.uom)
            else:
                line.product_uom_qty = float(line.product_qty)

    @api.depends('product_id', 'product_id.seller_ids', 'partner_id',
                 'product_qty', 'order_id.date_order', 'product_uom_id')
    def _compute_selected_seller_id(self):
        """≙ ``_compute_selected_seller_id`` (``:265-278``)."""
        for line in self:
            if line.product_id:
                params = line._get_select_sellers_params()
                order_date = line.order_id.date_order or timezone.now()
                seller = line.product_id._select_seller(
                    partner_id=line.partner_id,
                    # ``product_qty`` es ``Decimal`` aquí y ``Float`` en la
                    # fuente; ``_select_seller`` compara con ``float_compare``.
                    quantity=abs(float(line.product_qty or 0)),
                    date=timezone.localdate(order_date),
                    uom_id=line.product_uom_id,
                    params=params)
                # ``_select_seller`` devuelve la lista de a lo sumo uno
                # (``[:1]``) que aquí hace de recordset.
                line.selected_seller_id = seller[0] if seller else None
            else:
                line.selected_seller_id = None

    def _get_select_sellers_params(self):
        """≙ ``_get_select_sellers_params`` (``:753-758``)."""
        self.ensure_one()
        return {
            'order_id': self.order_id,
            'force_uom': True,
        }

    @api.depends('discount', 'price_unit')
    def _compute_price_unit_discounted(self):
        """≙ ``_compute_price_unit_discounted`` (``odoo19c: :152-155``)."""
        for line in self:
            line.price_unit_discounted = (
                line.price_unit or Decimal('0')) * (
                1 - (line.discount or Decimal('0')) / 100)

    @api.depends('product_uom_id', 'price_unit')
    def _compute_price_unit_product_uom(self):
        """≙ ``_compute_price_unit_product_uom`` (``odoo19c: :157-162``)."""
        for line in self:
            line.price_unit_product_uom = (
                not line.display_type and not line.is_downpayment
                and line.product_uom_id
                and line.product_uom_id._compute_price(
                    float(line.price_unit), line.product_id.uom)) or 0.0

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_ids',
                 'product_id.seller_ids',
                 'product_id.seller_ids.product_uom_id')
    def _compute_allowed_uom_ids(self):
        """≙ ``_compute_allowed_uom_ids`` (``odoo19c: :229-235``).

        La tarifa nombra su unidad ``product_uom`` y la plantilla sus
        unidades ``uom_ids``; ``uom`` es el ``uom_id`` del producto.
        """
        for line in self:
            product = line.product_id
            if not product:
                line.allowed_uom_ids = []
                continue
            seller_uoms = [
                seller.product_uom
                for seller in product.product_tmpl.seller_ids.all()
                if seller.product_uom_id and seller.product_id in {
                    None, product.pk}]
            units = [product.uom, *product.product_tmpl.uom_ids.all(),
                     *seller_uoms]
            line.allowed_uom_ids = list(dict.fromkeys(
                unit for unit in units if unit))

    @api.depends('product_id')
    def _compute_translated_product_name(self):
        """≙ ``_compute_translated_product_name`` (``odoo19c: :467-472``)."""
        for line in self:
            if not line.product_id:
                line.translated_product_name = False
                continue
            # ``product.product`` es un modelo de Django sin ``with_context``:
            # el contexto se fija con su equivalente en este ORM.
            with context_scope(lang=line.partner_id.lang
                               if line.partner_id else None):
                line.translated_product_name = line.product_id.display_name

    def _compute_parent_id(self):
        """≙ ``_compute_parent_id`` (``odoo19c: :510-529``)."""
        purchase_order_lines = set(self)
        for order, lines in self.grouped('order_id').items():
            if not order:
                for line in lines:
                    line.parent_id = None
                continue
            # Un Many2one de este ORM rechaza ``False``: el vacío es ``None``.
            last_section = None
            last_sub = None
            for line in order.order_line.sorted('sequence'):
                if line.display_type == 'line_section':
                    last_section = line
                    if line in purchase_order_lines:
                        line.parent_id = None
                    last_sub = None
                elif line.display_type == 'line_subsection':
                    if line in purchase_order_lines:
                        line.parent_id = last_section
                    last_sub = line
                elif line in purchase_order_lines:
                    line.parent_id = last_sub or last_section or None

    @api.depends('product_qty', 'price_unit', 'tax_ids', 'discount')
    def _compute_amount(self):
        """≙ ``_compute_amount`` (``odoo19c: :106-117``)."""
        AccountTax = apps.get_model('account', 'AccountTax')
        for line in self:
            company = line.company_id or env().company
            base_line = line._prepare_base_line_for_taxes_computation()
            AccountTax._add_tax_details_in_base_line(base_line, company)
            AccountTax._round_base_lines_tax_details([base_line], company)
            line.price_subtotal = (
                base_line['tax_details']['total_excluded_currency'])
            line.price_total = (
                base_line['tax_details']['total_included_currency'])
            line.price_tax = line.price_total - line.price_subtotal

    @api.depends('product_id', 'product_id.product_tmpl.type')
    def _compute_qty_received_method(self):
        """≙ ``odoo19c: :218-224``."""
        for line in self:
            if line.product_id and line.product_id.type in [
                    'consu', 'service']:
                line.qty_received_method = 'manual'
            else:
                line.qty_received_method = False

    @api.depends('qty_received_method', 'qty_received_manual')
    def _compute_qty_received(self):
        """≙ ``odoo19c: :226-231``."""
        received_qties = self._prepare_qty_received()
        for line in self:
            if not line.qty_received or line in received_qties:
                line.qty_received = received_qties[line]

    @api.depends('qty_received')
    @api.depends_context('accrual_entry_date')
    def _compute_qty_received_at_date(self):
        """≙ ``odoo19c: :233-242``."""
        if not self._date_in_the_past():
            for line in self:
                line.qty_received_at_date = line.qty_received
            return
        received_quantities = self._prepare_qty_received()
        for line in self:
            line.qty_received_at_date = received_quantities[line]

    def _prepare_qty_received(self):
        """≙ ``odoo19c: :244-251``. ``Decimal`` en vez de ``float``."""
        received_qties = defaultdict(Decimal)
        for line in self:
            if line.qty_received_method == 'manual':
                received_qties[line] = line.qty_received_manual or Decimal('0')
            else:
                received_qties[line] = Decimal('0')
        return received_qties

    @api.onchange('qty_received')
    def _inverse_qty_received(self):
        """≙ ``odoo19c: :253-263``. Con método ``manual`` el valor escrito va
        a ``qty_received_manual``; sin él, ésta queda en cero porque la
        cantidad la calcula otro mecanismo."""
        for line in self:
            if line.qty_received_method == 'manual':
                line.qty_received_manual = line.qty_received
            else:
                line.qty_received_manual = Decimal('0')

    @api.depends('invoice_lines.move.state', 'invoice_lines.quantity',
                 'qty_received', 'product_uom_qty', 'order_id.state')
    def _compute_qty_invoiced(self):
        """≙ ``odoo19c: :164-177``."""
        invoiced_quantities = self._prepare_qty_invoiced()
        for line in self:
            line.qty_invoiced = invoiced_quantities[line]
            if line.order_id.state == 'purchase':
                if line.product_id.purchase_method == 'purchase':
                    line.qty_to_invoice = (
                        (line.product_qty or Decimal('0'))
                        - line.qty_invoiced)
                else:
                    line.qty_to_invoice = (
                        (line.qty_received or Decimal('0'))
                        - line.qty_invoiced)
            else:
                line.qty_to_invoice = Decimal('0')

    @api.depends('qty_invoiced')
    @api.depends_context('accrual_entry_date')
    def _compute_qty_invoiced_at_date(self):
        """≙ ``odoo19c: :179-188``."""
        if not self._date_in_the_past():
            for line in self:
                line.qty_invoiced_at_date = line.qty_invoiced
            return
        invoiced_quantities = self._prepare_qty_invoiced()
        for line in self:
            line.qty_invoiced_at_date = invoiced_quantities[line]

    def _prepare_qty_invoiced(self):
        """≙ ``odoo19c: :190-200``. ``Decimal`` en vez de ``float``.

        Una línea de factura sin unidad es el recordset vacío de la fuente,
        cuyo ``_compute_quantity`` devuelve la cantidad tal cual.
        """
        invoiced_qties = defaultdict(Decimal)
        for line in self:
            for inv_line in line._get_invoice_lines():
                move = inv_line.move
                if (move.state not in ['cancel']
                        or move.payment_state == 'invoicing_legacy'):
                    uom = inv_line.product_uom_id
                    quantity = inv_line.quantity or Decimal('0')
                    if uom:
                        quantity = uom._compute_quantity(
                            quantity, line.product_uom_id)
                    if move.move_type == 'in_invoice':
                        invoiced_qties[line] += quantity
                    elif move.move_type == 'in_refund':
                        invoiced_qties[line] -= quantity
        return invoiced_qties

    def _get_invoice_lines(self):
        """≙ ``odoo19c: :202-211``.

        ``invoice_lines`` es el inverso de una FK de ``account.move.line``,
        un modelo de Django: el ``filtered`` de la fuente es aquí un filtro
        sobre su ``QuerySet``, con la misma condición.
        """
        self.ensure_one()
        move_line_model = type(self).invoice_lines.rel.related_model
        lines = move_line_model.objects.filter(
            purchase_line_id=self.id).select_related(
            'move', 'product_uom_id')
        if self.env.context.get('accrual_entry_date'):
            accrual_date = fields.Date.from_string(
                self.env.context['accrual_entry_date'])
            return lines.filter(move__invoice_date__isnull=False,
                                move__invoice_date__lte=accrual_date)
        return lines

    @api.depends('price_unit', 'qty_invoiced_at_date',
                 'qty_received_at_date')
    @api.depends_context('accrual_entry_date')
    def _compute_amount_to_invoice_at_date(self):
        """≙ ``odoo19c: :280-285``."""
        for line in self:
            qty_to_invoice = (
                (line.qty_received_at_date or Decimal('0'))
                - (line.qty_invoiced_at_date or Decimal('0')))
            if line.product_uom_id:
                qty_to_invoice = line.product_uom_id._compute_quantity(
                    qty_to_invoice, line.product_id.uom)
            line.amount_to_invoice_at_date = (
                qty_to_invoice * line._get_gross_price_unit())

    def _get_gross_price_unit(self):
        """≙ ``odoo19c: :492-508``."""
        self.ensure_one()
        price_unit = self.price_unit or Decimal('0')
        if self.discount:
            price_unit = price_unit * (1 - self.discount / 100)
        taxes = self.tax_ids.all()
        if taxes:
            qty = self.product_qty or 1
            price_unit = taxes.compute_all(
                price_unit,
                currency=self.order_id.currency_id,
                quantity=qty,
                rounding_method='round_globally',
            )['total_void']
            price_unit = price_unit / qty
        product_uom = self.product_id.uom
        if self.product_uom_id and product_uom and (
                self.product_uom_id.pk != product_uom.pk):
            price_unit *= Decimal(repr(
                product_uom.factor / self.product_uom_id.factor))
        return price_unit

    def _track_qty_received(self, new_qty):
        """≙ ``odoo19c: :714-728``. Publica en la orden la nota del cambio de
        cantidad recibida, salvo desde el asistente de devengo
        (``accrual_entry_date``), que sólo calcula a una fecha pasada."""
        self.ensure_one()
        if self.env.context.get('accrual_entry_date'):
            return
        if (new_qty != self.qty_received
                and self.order_id.state == 'purchase'):
            self.order_id.message_post_with_source(
                'purchase.track_po_line_qty_received_template',
                render_values={'line': self, 'qty_received': new_qty},
                subtype_xmlid='mail.mt_note',
            )

    @api.model
    def _date_in_the_past(self):
        """≙ ``odoo19c: :707-712``."""
        if 'accrual_entry_date' not in self.env.context:
            return False
        accrual_date = fields.Date.from_string(
            self.env.context['accrual_entry_date'])
        return bool(accrual_date) and accrual_date < fields.Date.today()

    def _prepare_base_line_for_taxes_computation(self):
        """ Convert the current record to a dictionary in order to use the
        generic taxes computation method defined on account.tax.

        ≙ ``odoo19c: :119-136``.

        :return: A python dictionary.
        """
        self.ensure_one()
        order = self.order_id
        company = order.company_id or env().company
        AccountTax = apps.get_model('account', 'AccountTax')
        return AccountTax._prepare_base_line_for_taxes_computation(
            self,
            tax_ids=self.tax_ids.all(),
            quantity=self.product_qty,
            partner_id=order.partner_id,
            currency_id=order.currency_id or company.currency,
            rate=order.currency_rate,
            name=self.name,
        )

    # --- Precio, fecha prevista y descripción (purchase-line-price-and-dates)
    #
    # Al final del cuerpo de la clase por la admisión de estilo, que fecha
    # cada infracción heredada por su posición en el contenedor.

    #: ≙ ``date_planned`` (``odoo19c: :25-28``).
    date_planned = fields.Datetime(
        'Expected Arrival', db_index=True, null=True, blank=True,
        compute='_compute_price_unit_and_date_planned_and_name', store=True,
        readonly=False,
        help_text=(
            'Delivery date expected from vendor. This date respectively '
            "defaults to vendor pricelist lead time then today's date."))

    def _compute_tax_id(self):
        """≙ ``_compute_tax_id`` (``odoo19c: :146-152``).

        ``line.with_company(line.company_id)`` es ``company_scope``.
        """
        AccountTax = apps.get_model('account', 'AccountTax')
        for line in self:
            scope = (company_scope(line.company_id_id)
                     if line.company_id_id else nullcontext())
            with scope:
                order = line.order_id
                fpos = order.fiscal_position_id or (
                    AccountFiscalPosition._get_fiscal_position(
                        order.partner_id))
                # filter taxes by company
                taxes = AccountTax.objects.filter(
                    pk__in=line.product_id.supplier_taxes.values('pk'),
                )._filter_taxes_by_company(line.company_id)
                line.tax_ids = fpos.map_tax(taxes)

    @api.model
    def _get_date_planned(self, seller, po=False):
        """Return the datetime value to use as Schedule Date
        (``date_planned``) for PO Lines that correspond to the given
        product.seller_ids, when ordered at `date_order_str`.

        ≙ ``_get_date_planned`` (``odoo19c: :334-351``).

        :param Model seller: used to fetch the delivery delay (if no seller
                             is provided, the delay is 0)
        :param Model po: purchase.order, necessary only if the PO line is
                         not yet attached to a PO.
        :rtype: datetime
        :return: desired Schedule Date for the PO line
        """
        date_order = (po.date_order if po
                      else self.order_id.date_order if self.order_id_id
                      else None)
        delay = relativedelta(days=seller.delay if seller else 0)
        if date_order:
            return date_order + delay
        return datetime.today() + delay

    @api.onchange('product_id')
    def onchange_product_id(self):
        """≙ ``onchange_product_id`` (``odoo19c: :366-380``)."""
        # TODO: Remove when onchanges are replaced with computes
        if not self.product_id:
            return
        if self.env.context.get('origin_po_id') and self.product_qty:
            self._compute_tax_id()
            return

        # Reset date, price and quantity since _onchange_quantity will
        # provide default values
        self.price_unit = self.product_qty = self.technical_price_unit = (
            Decimal('0'))

        self._product_id_change()

        self._suggest_quantity()

    def _product_id_change(self):
        """≙ ``_product_id_change`` (``odoo19c: :382-395``).

        ``product_id.with_context(lang=…, partner_id=None, company_id=…)``
        es ``context_scope`` sobre el mismo producto.
        """
        if not self.product_id:
            return

        self.product_uom_id = self.product_id.uom
        with context_scope(
                lang=get_lang(self.env, self.partner_id.lang
                              if self.partner_id else None).code,
                partner_id=None, company_id=self.company_id_id):
            self.name = self._get_product_purchase_description(
                self.product_id)

        self._compute_tax_id()

    @api.depends('product_qty', 'product_uom_id', 'company_id',
                 'order_id.partner_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        """≙ ``_compute_price_unit_and_date_planned_and_name``
        (``odoo19c: :404-468``).

        El ``strftime(DEFAULT_SERVER_DATETIME_FORMAT)`` de la fuente existe
        porque su caché guarda cadenas; aquí se asigna el ``datetime``. El
        ``product_id.with_context(seller_id=…, lang=…)`` es ``context_scope``
        sobre el mismo producto. ``price_unit`` y ``technical_price_unit``
        se comparan con el falso como cero, que es como la fuente lee un
        ``Float`` vacío.
        """
        AccountTax = apps.get_model('account', 'AccountTax')
        for line in self:
            # Una línea sin guardar no tiene facturas ni impuestos todavía:
            # sus x2many son el recordset vacío de la fuente.
            line_taxes = (line.tax_ids.all() if line.pk
                          else AccountTax.objects.none())
            if (not line.product_id
                    or (line.pk and line.invoice_lines.exists())
                    or not line.company_id
                    or self.env.context.get('skip_uom_conversion')
                    or ((line.technical_price_unit or 0)
                        != (line.price_unit or 0))):
                continue
            params = line._get_select_sellers_params()
            seller = line.selected_seller_id

            if seller or not line.date_planned:
                line.date_planned = line._get_date_planned(seller)

            lang = get_lang(line.env, line.partner_id.lang
                            if line.partner_id else None).code
            # record product names to avoid resetting custom descriptions
            default_names = []
            display_names = []
            vendors = line.product_id._prepare_sellers(params=params)
            with context_scope(seller_id=None, partner_id=None, lang=lang):
                without_seller_name = line.product_id.display_name
                default_names.append(
                    line._get_product_purchase_description(line.product_id))
            for vendor in vendors:
                with context_scope(seller_id=vendor.pk, lang=lang):
                    default_names.append(
                        line._get_product_purchase_description(
                            line.product_id))
                    display_names.append(line.product_id.display_name)
            if not line.name or line.name in default_names:
                with context_scope(
                        seller_id=seller.pk if seller else None, lang=lang):
                    line.name = line._get_product_purchase_description(
                        line.product_id)
            else:
                # Checks that the product vendor and vendor name are correct
                vendor_ids = [vendor.pk for vendor in vendors]
                for vendor, display_name in zip(vendors, display_names):
                    if line.name.startswith(display_name):
                        if not seller:
                            line.name = (without_seller_name
                                         + line.name[len(display_name):])
                        elif vendor.pk != seller.pk:
                            line.name = (
                                display_names[vendor_ids.index(seller.pk)]
                                + line.name[len(display_name):])
                        break

            # If not seller, use the standard price. It needs a proper
            # currency conversion.
            product = line.product_id
            if not seller:
                partner = line.order_id.partner_id
                unavailable_seller = [
                    info for info in product.product_tmpl.seller_ids.all()
                    if partner is not None
                    and info.partner_id_id == partner.pk]
                if (not unavailable_seller and line.price_unit
                        and line.product_uom_id_id
                        == line._origin.product_uom_id_id):
                    # Avoid to modify the price unit if there is no price
                    # list for this partner and the line has already one to
                    # avoid to override unit price set manually.
                    continue
                line.discount = Decimal('0')
                po_line_uom = line.product_uom_id or product.uom
                price_unit = AccountTax._fix_tax_included_price_company(
                    product.uom._compute_price(
                        product.standard_price, po_line_uom),
                    product.supplier_taxes.all(),
                    line_taxes,
                    line.company_id,
                )
                # ``cost_currency_id`` es aquí la propiedad ``cost_currency``
                # de la plantilla.
                line._reset_price_unit(
                    product.product_tmpl.cost_currency._convert(
                        price_unit, line.currency_id, line.company_id,
                        line.date_order or timezone.localdate(), False))
            else:
                price_unit = AccountTax._fix_tax_included_price_company(
                    seller.price, product.supplier_taxes.all(),
                    line_taxes, line.company_id)
                price_unit = seller.currency._convert(
                    price_unit, line.currency_id, line.company_id,
                    line.date_order or timezone.localdate(), False)
                line._reset_price_unit(seller.product_uom._compute_price(
                    price_unit, line.product_uom_id))
                line.discount = seller.discount or Decimal('0')

    def _reset_price_unit(self, price_unit):
        """≙ ``_reset_price_unit`` (``odoo19c: :470-475``).

        """
        self.ensure_one()
        self.update({
            'price_unit': price_unit,
            'technical_price_unit': price_unit,
        })

    def _suggest_quantity(self):
        """Suggest a minimal quantity based on the seller

        ≙ ``_suggest_quantity`` (``odoo19c: :535-551``).
        """
        if not self.product_id:
            return
        date = (self.order_id.date_order and self.order_id.date_order.date()
                or timezone.localdate())
        partner = self.order_id.partner_id
        seller_min_qty = sorted(
            (info for info in self.product_id.product_tmpl.seller_ids.all()
             if partner is not None and info.partner_id_id == partner.pk
             and (not info.product_id or info.product_id == self.product_id.pk)
             and (not info.date_start or info.date_start <= date)
             and (not info.date_end or info.date_end >= date)),
            key=lambda info: info.min_qty)
        if seller_min_qty:
            self.product_qty = seller_min_qty[0].min_qty or Decimal('1')
            self.product_uom_id = seller_min_qty[0].product_uom
        else:
            self.product_qty = Decimal('1')

    def _get_product_purchase_description(self, product_lang):
        """≙ ``_get_product_purchase_description`` (``odoo19c: :602-611``).

        ``product_lang`` es el producto leído en el contexto que el llamador
        abrió con ``context_scope``.
        """
        self.ensure_one()
        name = product_lang.display_name
        if product_lang.description_purchase:
            name += '\n' + product_lang.description_purchase
        for no_variant_attribute_value in (
                self.product_no_variant_attribute_value_ids.all()):
            name += ("\n" + no_variant_attribute_value.attribute_id.name
                     + ': ' + no_variant_attribute_value.name)

        return name

    def _convert_to_middle_of_day(self, date):
        """Return a datetime which is the noon of the input date(time)
        according to order user's time zone, convert to UTC time.

        ≙ ``_convert_to_middle_of_day`` (``odoo19c: :701-705``).
        """
        return self.order_id.get_order_timezone().localize(
            datetime.combine(date, time(12))).astimezone(UTC).replace(
                tzinfo=None)

    def _update_date_planned(self, updated_date):
        """≙ ``_update_date_planned`` (``odoo19c: :714-715``)."""
        self.date_planned = updated_date
