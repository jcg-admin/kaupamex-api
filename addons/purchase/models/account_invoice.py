"""Lo que ``purchase`` cuelga en ``account.move.line``.

≙ ``class AccountMoveLine`` con ``_inherit = 'account.move.line'``
(``odoo19c: addons/purchase/models/account_invoice.py:523-560``). LGPL-3
según su ``__manifest__.py``: copia y adaptación con atribución.

El modelo es de Django en ``account``; los campos se cuelgan con
:func:`~orm.model_classes.extend_model` desde ``PurchaseConfig.ready()``, y la
migración vive en ``account`` con dependencia hacia ``purchase`` (el
precedente es ``fleet.0004``, que depende de ``hr``).

De los seis símbolos de la clase se portan tres:

* ``is_downpayment`` (``:527``);
* ``purchase_line_id`` (``:528``), con ``related_name='invoice_lines'``, que
  es el ``One2many`` de ``purchase_order_line.py:56``;
* ``purchase_order_id`` (``:529``), relacionado y sin columna.

**El disparo de ``purchase.order.invoice_ids``.** En la fuente, crear,
escribir o borrar una línea de factura anuncia ``purchase_line_id`` y la
orden recalcula sus facturas (``@api.depends('order_line.invoice_lines.
move_id')``, ``purchase_order.py:70``). Aquí ``account.move.line`` es un
modelo de Django sin el mixin de acceso: sus filas nacen por
``objects.create``, que no anuncia nada, y ``create`` del ORM le exige
``_check_field_access``. El anuncio se hace desde sus señales: las órdenes
afectadas, la anterior y la nueva, quedan en ``env.add_to_compute`` para los
dos campos, que es el recálculo pendiente de la fuente.

Pendientes, cada uno con su fila en el plan:

* pendiente: ``purchase_line_warn_msg`` y su cómputo (``:530,556-560``):
  lee ``product.purchase_line_warn_msg``, que cuelga
  ``purchase/models/product.py`` y no está portado; unidad
  ``purchase-product-0397``.
* pendiente: ``_copy_data_extend_business_fields`` (``:532-535``): extiende
  un método de ``account.move.line`` que no existe en este árbol (medido:
  0 hits en ``addons/account``); unidad
  ``account-copy-data-business-fields-0397``.
* pendiente: ``_prepare_line_values_for_purchase`` (``:537-...``): su
  consumidor es la creación de órdenes desde facturas, que no está portada;
  unidad ``purchase-from-bill-0397``.
"""
from django.apps import apps
from django.db import models as dj_models
from django.db.models.signals import post_delete, post_save, pre_save

import fields
from orm.environments import env
from orm.model_classes import extend_model

#: Atributo con que ``pre_save`` deja en la fila la orden que tenía antes.
_PREVIOUS_ORDER = '_purchase_previous_order_id'


def _order_id_of(line):
    """La orden de la línea de compra a la que apunta ``line``, o ``None``."""
    purchase_line_pk = line.__dict__.get('purchase_line_id_id')
    if not purchase_line_pk:
        return None
    line_model = apps.get_model('purchase', 'PurchaseOrderLine')
    return line_model.objects.filter(pk=purchase_line_pk).values_list(
        'order_id', flat=True).first()


def _remember_previous_order(sender, instance, **kwargs):
    """``pre_save``: la orden que la fila tenía antes de esta escritura."""
    previous = None
    if instance.pk:
        stored = sender.objects.filter(pk=instance.pk).values_list(
            'purchase_line_id__order_id', flat=True).first()
        previous = stored
    instance.__dict__[_PREVIOUS_ORDER] = previous


def _mark_orders_to_compute(order_ids):
    """Deja los dos campos de facturas pendientes de cálculo."""
    order_ids = {order_id for order_id in order_ids if order_id}
    if not order_ids:
        return
    order_model = apps.get_model('purchase', 'PurchaseOrder')
    environment = env()
    for name in ('invoice_ids', 'invoice_count'):
        environment.add_to_compute(order_model._meta.get_field(name),
                                   order_ids)


def _announce_saved_line(sender, instance, **kwargs):
    """``post_save``: la orden anterior y la nueva recalculan."""
    _mark_orders_to_compute((instance.__dict__.pop(_PREVIOUS_ORDER, None),
                             _order_id_of(instance)))


def _announce_deleted_line(sender, instance, **kwargs):
    """``post_delete``: la orden que tenía la fila recalcula."""
    _mark_orders_to_compute((instance.__dict__.get(_PREVIOUS_ORDER)
                             or _order_id_of(instance),))


def apply_account_move_line_extensions():
    """≙ ``_inherit = 'account.move.line'`` de ``purchase``."""
    extend_model(
        'account', 'AccountMoveLine',
        campos={
            'is_downpayment': fields.Boolean(default=False),
            'purchase_line_id': fields.Many2one(
                'purchase.PurchaseOrderLine',
                verbose_name='Purchase Order Line',
                null=True, blank=True, on_delete=dj_models.SET_NULL,
                related_name='invoice_lines', db_index=True, copy=False,
                db_column='purchase_line_id'),
            'purchase_order_id': fields.Many2one(
                'purchase.PurchaseOrder', verbose_name='Purchase Order',
                related='purchase_line_id.order_id', store=False,
                on_delete=dj_models.SET_NULL, related_name='+'),
        },
    )
    line_model = apps.get_model('account', 'AccountMoveLine')
    pre_save.connect(_remember_previous_order, sender=line_model,
                     dispatch_uid='purchase_invoice_previous_order')
    post_save.connect(_announce_saved_line, sender=line_model,
                      dispatch_uid='purchase_invoice_saved_line')
    post_delete.connect(_announce_deleted_line, sender=line_model,
                        dispatch_uid='purchase_invoice_deleted_line')
