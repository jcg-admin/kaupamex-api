"""Lo que ``purchase`` cuelga en ``product`` — ≙ ``_inherit`` de tres clases.

Adaptación de ``odoo19c: addons/purchase/models/product.py`` (LGPL-3 según su
``__manifest__.py``: copia y adaptación con atribución). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-product.md``.

*Métrica:* símbolos de las tres clases, contados por AST: 15. Se portan 10
aquí; los 5 que necesitan piezas ausentes son la unidad
``purchase-product-actions-0397``, cada uno con su causa:

* pendiente: ``ProductTemplate.action_view_po`` y
  ``ProductProduct.action_view_po`` (``:47-54,107-111``) — la acción
  ``purchase.action_purchase_history`` no está sembrada;
* pendiente: ``ProductTemplate._get_backend_root_menu_ids`` y
  ``ProductProduct._get_backend_root_menu_ids`` (``:34-35,113-114``) — la
  base no existe en ``product`` ni el menú ``purchase.menu_purchase_root``;
* pendiente: ``ProductTemplate.get_import_templates`` (``:37-45``) — la
  plantilla XLS estática no existe;
* pendiente: ``ProductSupplierinfo._onchange_partner_id`` (``:146-148``) —
  lee ``property_purchase_currency_id`` de ``res.partner``, que no existe.

``_inherit`` se expresa con :func:`~orm.model_classes.extend_model`; donde la
fuente llama a ``super()`` se usa :func:`~orm.method_chain.wrap_method`, que
entrega la implementación previa. En ``product`` los FK de Django se llaman
sin sufijo (``uom``, ``product_tmpl``): ``uom_id`` es su ``attname``. Los
cómputos operan sobre una fila: el ORM
invoca el de un modelo de Django por instancia (``orm/models.py``,
``_run_precompute_field``), la misma forma que ``_compute_balance`` de
``account.move.line``.
"""
import datetime

from django.apps import apps
from django.utils import timezone

import api
import fields
from exceptions import UserError
from orm.environments import env, get_current_user
from orm.method_chain import wrap_method
from orm.model_classes import extend_model
from tools.translate import _

#: ≙ el ``selection`` de ``purchase_method`` (``odoo19c: :14-17``).
PURCHASE_METHODS = [
    ('purchase', 'On ordered quantities'),
    ('receive', 'On received quantities'),
]


def _line_model():
    return apps.get_model('purchase', 'PurchaseOrderLine')


def _group_record(value):
    """El registro de un grupo de ``_read_group``.

    Agrupado por un FK hacia un modelo de Django (``product.product``,
    ``uom.uom``), el puerto entrega el grupo como un ``QuerySet`` de una fila
    donde la fuente entrega un registro; se desenvuelve.
    """
    return value.first() if hasattr(value, 'first') else value


# --- product.template ----------------------------------------------------

@api.depends('type')
def _compute_purchase_method(self):
    """≙ ``_compute_purchase_method`` (``odoo19c: :22-28``)."""
    default = type(self)._meta.get_field('purchase_method').get_default() \
        or 'receive'
    self.purchase_method = 'purchase' if self.type == 'service' else default


def _compute_template_purchased_product_qty(self):
    """≙ ``ProductTemplate._compute_purchased_product_qty`` (``:30-32``).

    ``with_context(active_test=False)``: se suman también las variantes
    archivadas, así que se leen por ``_base_manager``.
    """
    variants = apps.get_model('product', 'ProductProduct')._base_manager \
        .filter(product_tmpl_id=self)
    total = sum(variant.purchased_product_qty for variant in variants)
    self.purchased_product_qty = (
        self.uom.round(total) if self.uom else total)


# --- product.product ------------------------------------------------------

def _compute_purchased_product_qty(self):
    """≙ ``ProductProduct._compute_purchased_product_qty`` (``:69-82``)."""
    date_from = timezone.localdate() - datetime.timedelta(days=365)
    domain = [
        ('order_id.state', '=', 'purchase'),
        ('product_id', 'in', [self.pk]),
        ('order_id.date_approve', '>=', date_from),
    ]
    order_lines = _line_model()._read_group(
        domain, ['product_id'], ['product_uom_qty:sum'])
    purchased_data = {_group_record(product).pk: qty
                      for product, qty in order_lines}
    if not self.pk:
        self.purchased_product_qty = 0.0
        return
    qty = purchased_data.get(self.pk, 0) or 0
    self.purchased_product_qty = (
        self.uom.round(qty) if self.uom else qty)


@api.depends_context('order_id')
def _compute_is_in_purchase_order(self):
    """≙ ``_compute_is_in_purchase_order`` (``:84-98``)."""
    order_id = env().context.get('order_id')
    if not order_id:
        self.is_in_purchase_order = False
        return
    read_group_data = _line_model()._read_group(
        domain=[('order_id', '=', order_id)],
        groupby=['product_id'],
        aggregates=['__count'],
    )
    data = {_group_record(product).pk: count
            for product, count in read_group_data}
    self.is_in_purchase_order = bool(data.get(self.pk, 0))


def _search_is_in_purchase_order(cls, operator, value):
    """≙ ``_search_is_in_purchase_order`` (``:100-105``)."""
    if operator != 'in':
        return NotImplemented
    product_ids = list(_line_model().objects.filter(
        order_id__in=[env().context.get('order_id') or 0],
    ).values_list('product_id', flat=True).distinct())
    return [('id', 'in', [pk for pk in product_ids if pk])]


def _update_uom(self, previous, to_uom_id):
    """≙ ``_update_uom`` (``odoo19c: :116-131``)."""
    line_model = _line_model()
    for uom, product, po_lines in line_model._read_group(
        [('product_id', 'in', [self.pk])],
        ['product_uom_id', 'product_id'],
        ['id:recordset'],
    ):
        uom, product = _group_record(uom), _group_record(product)
        template_uom = product.product_tmpl_id.uom
        if uom != template_uom:
            raise UserError(_(
                'As other units of measure (ex : %(problem_uom)s) '
                'than %(uom)s have already been used for this product, the '
                'change of unit of measure can not be done.'
                'If you want to change it, please archive the product and '
                'create a new one.',
                problem_uom=uom.display_name,
                uom=template_uom.display_name))
        po_lines.write(
            {'product_uom_id': getattr(to_uom_id, 'pk', to_uom_id)})
        po_lines.flush_recordset()
    return previous(to_uom_id)


def _trigger_uom_warning(self, previous):
    """≙ ``_trigger_uom_warning`` (``odoo19c: :133-140``)."""
    res = previous()
    if res:
        return res
    return _line_model()._base_manager.filter(product_id=self.pk).exists()


# --- product.supplierinfo -------------------------------------------------

def _get_filtered_supplier(cls, previous, sellers, company_id, product_id,
                           params=False):
    """≙ ``_get_filtered_supplier`` (``odoo19c: :150-153``)."""
    # En la fuente ``params['order_id']`` es un registro, vacío si no hay
    # orden; aquí el vacío llega como ``None``.
    order = params.get('order_id') if params else None
    if order is not None and order.company_id:
        company_id = order.company_id
    return previous(sellers, company_id, product_id, params)


# --- account.move.line (account_invoice.py:530,556-560) -------------------

@api.depends('product_id.purchase_line_warn_msg')
def _compute_purchase_line_warn_msg(self):
    """≙ ``_compute_purchase_line_warn_msg`` (``odoo19c: account_invoice.py:
    556-560``)."""
    user = get_current_user()
    has_group = bool(user) and user.has_group(
        'purchase.group_warning_purchase')
    product = self.product_id
    self.purchase_line_warn_msg = (
        product.product_tmpl_id.purchase_line_warn_msg or ''
        if has_group and product else '')


def apply_purchase_product_extensions():
    """≙ ``_inherit`` de ``product.template``, ``product.product`` y
    ``product.supplierinfo``, y el aviso de la línea de factura.

    La invoca ``PurchaseConfig.ready()``: en tiempo de import el registro de
    modelos aún no está poblado.
    """
    extend_model(
        'product', 'ProductTemplate',
        campos={
            'purchased_product_qty': fields.Float(
                'Purchased', compute='_compute_purchased_product_qty',
                digits='Product Unit'),
            'purchase_method': fields.Selection(
                PURCHASE_METHODS, 'Control Policy',
                compute='_compute_purchase_method', precompute=True,
                store=True, readonly=False, max_length=8, default='receive',
                help_text=(
                    'On ordered quantities: Control bills based on ordered '
                    'quantities.\nOn received quantities: Control bills '
                    'based on received quantities.')),
            'purchase_line_warn_msg': fields.Text(
                'Message for Purchase Order Line', null=True, blank=True),
        },
        metodos={
            '_compute_purchase_method': _compute_purchase_method,
            '_compute_purchased_product_qty': (
                _compute_template_purchased_product_qty),
        },
    )
    extend_model(
        'product', 'ProductProduct',
        campos={
            'purchased_product_qty': fields.Float(
                'Purchased', compute='_compute_purchased_product_qty',
                digits='Product Unit'),
            'is_in_purchase_order': fields.Boolean(
                compute='_compute_is_in_purchase_order',
                search='_search_is_in_purchase_order'),
        },
        metodos={
            '_compute_purchased_product_qty': _compute_purchased_product_qty,
            '_compute_is_in_purchase_order': _compute_is_in_purchase_order,
            '_search_is_in_purchase_order': classmethod(
                _search_is_in_purchase_order),
        },
        luego=lambda model: (
            wrap_method(model, '_update_uom', _update_uom),
            wrap_method(model, '_trigger_uom_warning', _trigger_uom_warning)),
    )
    wrap_method(apps.get_model('product', 'ProductSupplierinfo'),
                '_get_filtered_supplier', classmethod(_get_filtered_supplier))
    extend_model(
        'account', 'AccountMoveLine',
        campos={
            'purchase_line_warn_msg': fields.Text(
                compute='_compute_purchase_line_warn_msg', store=False),
        },
        metodos={
            '_compute_purchase_line_warn_msg': (
                _compute_purchase_line_warn_msg),
        },
    )
