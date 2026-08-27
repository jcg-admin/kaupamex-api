"""``purchase.order.line`` — la línea de compra que mueve mercancía
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/purchase_order_line.py``
(``odoo19c: addons/purchase_stock/models/purchase_order_line.py``, 428 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: la línea deja de ser una fila de un documento y pasa a ser el origen
de movimientos de inventario. Gana el enlace con los movimientos que la sirven
(``move_ids``), con los que ella misma disparó (``move_dest_ids``, el caso
*make-to-order*), con el punto de pedido que la generó, y la política de qué
hacer con esos movimientos cuando la línea se cancela.

Porte símbolo por símbolo — 9 de 36
=====================================

*Métrica:* entradas del cuerpo de ``class PurchaseOrderLine`` contadas por AST
sobre la fuente. Son **37** con ``_inherit``; **36** sin él: 9 campos y 27
métodos (el AST cuenta ``_ondelete_stock_moves`` entre ellos porque la fuente
lo declara **antes** de los campos, para usarlo como valor de ``ondelete=``).
*Ciega a:* si un símbolo portado se comporta igual en ejecución.

Lo portado
------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Forma aquí
   * - ``orderpoint_id`` (``:29``)
     - campo ``orderpoint`` (FK, ``SET_NULL``, indexado)
   * - ``product_description_variants`` (``:31``)
     - campo ``Char``
   * - ``propagate_cancel`` (``:32``)
     - campo ``Boolean``, ``default=True``
   * - ``location_final_id`` (``:35``)
     - campo ``location_final`` (FK a ``stock.StockLocation``)
   * - ``is_storable`` (``:34``)
     - ``property`` (era ``related=``)
   * - ``_get_po_line_moves`` (``:42-48``)
     - método homónimo
   * - ``_update_move_date_deadline`` (``:161-168``)
     - método homónimo
   * - ``_check_orderpoint_picking_type`` (``:266-271``)
     - método homónimo
   * - ``unlink`` (``:139-155``)
     - ``chain_method`` sobre ``delete`` — D-2

Los dos campos que **ya existen** y no se redeclaran
------------------------------------------------------

- ``move_ids`` (``:28``) — ``One2many('stock.move', 'purchase_line_id')``. El
  reverso lo produce ``StockMove.purchase_line``, declarado en
  ``stock_move.py`` de este addon con ``related_name='move_ids'``.
- ``move_dest_ids`` (``:30``) — la **otra mitad** del M2M
  ``stock_move_created_purchase_line_rel``, cuyo lado ``stock.move`` es
  ``created_purchase_line_ids``. Django declara la relación una vez; se
  declaró allá con ``related_name='move_dest_ids'``, así que
  ``line.move_dest_ids`` se lee igual que en la fuente. Redeclararla aquí
  produciría **dos tablas** para la misma relación — el mismo criterio que
  ``addons/stock/models/stock_reference.py`` documentó para ``move_ids``.

Lo NO portado, agrupado por causa
-----------------------------------

**Causa A — la línea de compra de este árbol tiene seis campos.**
``addons/purchase/models/purchase_order_line.py`` (65 líneas) declara
``order``, ``product``, ``name``, ``product_qty``, ``price_unit`` y
``discount``. Los siguientes símbolos leen o escriben campos que **no
existen** y que pertenecen al addon ``purchase``, fuera del write-set:

.. code-block:: text

    qty_received · qty_received_manual · qty_received_method · qty_invoiced ·
    qty_to_invoice · product_uom_id · product_uom_qty · date_planned ·
    state · display_type · sequence · tax_ids · invoice_lines ·
    price_unit_discounted · currency_id · company_id

Caen aquí, con la línea de la fuente: ``_ondelete_stock_moves`` (``:13-23``),
``qty_received_method`` (``:25-26``), ``_compute_qty_received_method``
(``:37-41``), ``_compute_qty_received`` (``:50-53``), ``_prepare_qty_received``
(``:55-78``), ``forecasted_issue`` + ``_compute_forecasted_issue``
(``:33``, ``:80-90``), ``create`` (``:92-97``), ``write`` (``:99-121``),
``_create_or_update_picking`` (``:170-198``),
``_get_move_dests_initial_demand`` (``:200-203``), ``_prepare_stock_moves``
(``:205-235``), ``_get_stock_move_price_unit`` (``:237-259``),
``_get_qty_procurement`` (``:261-264``), ``_prepare_stock_move_vals``
(``:273-314``), ``_prepare_account_move_line`` (``:316-330``),
``_prepare_purchase_order_line_from_procurement`` (``:332-362``),
``_create_stock_moves`` (``:364-370``), ``_find_candidate`` (``:372-397``),
``_update_date_planned`` (``:412-418``), ``_update_qty_received_method``
(``:420-424``), ``_merge_po_line`` (``:426-428``).

**Causa B — ``to_refund`` no existe.** Medido:
``grep -rn "to_refund" addons/ src/ --include=*.py`` → **0**. Es la bandera de
``stock.move`` que distingue una devolución que se reembolsa de una que no, y
la declara ``stock_account`` en la referencia. Cae
``_get_outgoing_incoming_moves`` (``:399-410``), cuyas dos ramas la consultan.

**Causa C — ``_for_xml_id`` no existe** (0 definiciones):
``action_product_forecast_report`` (``:123-137``) devuelve el descriptor de una
acción de ventana resuelta por XML ID.

Divergencias declaradas
========================

**D-1 — ``is_storable`` es ``property``, no ``related``.** La fuente lo declara
``related='product_id.is_storable'``, que sin ``store=True`` no tiene columna
allá tampoco. Aquí es una ``property`` que lee la del producto — que a su vez
ya es una ``property`` que ``stock`` cuelga sobre ``product.product``
(``addons/stock/models/product.py``).

**D-2 — ``unlink`` se porta encadenando ``delete``.** Este ORM no tiene
``unlink``: el borrado es ``Model.delete()`` de Django, y el árbol ya usa ese
nombre (``StockMove.delete``, ``StockPicking.delete``). La función portada
ejecuta los cuatro efectos de la fuente y **devuelve ``None``**, con lo que
``chain_method`` ejecuta a continuación el ``delete`` previo — que es
exactamente lo que ``return super().unlink()`` hace en la última línea de la
fuente.

**D-3 — ``_check_orderpoint_picking_type`` levanta ``ValidationError``, no
``UserError``.** La fuente usa ``odoo.exceptions.UserError``; el equivalente de
este stack para un error de negocio que la vista traduce a 400 es
``django.core.exceptions.ValidationError``, que es lo que
``addons/purchase/models/purchase_order.py:90`` ya usa. El mensaje se conserva
con sus cuatro variables.
"""
from django.core.exceptions import ValidationError

import fields
import models
from orm.method_chain import chain_method
from orm.model_classes import extend_model


def is_storable(self):
    """≙ ``is_storable`` (``odoo19c: :34``) — D-1 del docstring."""
    return bool(self.product.is_storable) if self.product_id else False


def _get_po_line_moves(self):
    """≙ ``_get_po_line_moves`` (``odoo19c: :42-48``).

    Los movimientos de esta línea que son **del mismo producto**. El filtro no
    es redundante: con una lista de materiales en kit los productos entregados
    no coinciden con los de la orden.

    **Bloqueada la rama de ``accrual_entry_date``**: la fuente acota además por
    una fecha que llega en el contexto, y ese contexto lo pone el asistente de
    devengos de ``account`` (``accrued_orders.py``), que no invoca a este
    método en este árbol. Sin llamador, el filtro no tiene con qué acotarse.
    """
    return self.move_ids.filter(product=self.product)


def _update_move_date_deadline(self, new_date):
    """≙ ``_update_move_date_deadline`` (``odoo19c: :161-168``).

    «Updates corresponding move picking line deadline dates that are not yet
    completed.» Si la línea no tiene movimientos propios pendientes, la fuente
    cae a los movimientos **destino** — los que esta línea abastece.
    """
    pending_moves = list(self.move_ids.exclude(state__in=('done', 'cancel')))
    if not pending_moves:
        pending_moves = list(self.move_dest_ids.exclude(state__in=('done', 'cancel')))
    for move in pending_moves:
        move.date_deadline = new_date
        move.save(update_fields=['date_deadline', 'updated_at'])


def _check_orderpoint_picking_type(self):
    """≙ ``_check_orderpoint_picking_type`` (``odoo19c: :266-271``).

    El almacén del tipo de operación tiene que contener la ubicación de la
    regla de reabastecimiento. Si no, la orden se recibiría en un almacén y la
    regla esperaría la mercancía en otro — de ahí que la fuente prefiera
    reventar a crear una inconsistencia silenciosa.

    D-3: ``ValidationError`` en vez de ``UserError``.
    """
    picking_type = self.order.picking_type if self.order_id else None
    warehouse = picking_type.warehouse if picking_type is not None else None
    warehouse_loc = warehouse.view_location if warehouse is not None else None

    destination_loc = self.move_dest_ids.first()
    dest_loc = destination_loc.location if destination_loc is not None else None
    if dest_loc is None and self.orderpoint_id:
        dest_loc = self.orderpoint.location

    if (warehouse_loc is not None and dest_loc is not None
            and dest_loc.warehouse_id
            and warehouse_loc.parent_path not in (dest_loc.parent_path or '')):
        raise ValidationError(
            f'El almacén del tipo de operación ({picking_type}) es '
            f'incoherente con la ubicación ({dest_loc}) de la regla de '
            f'reabastecimiento ({self.orderpoint}) para el producto '
            f'{self.product}. Cambia el tipo de operación o cancela la '
            f'solicitud de cotización.')


def delete_cancelling_moves(self, *args, **kwargs):
    """≙ ``unlink`` (``odoo19c: :139-155``) — D-2 del docstring.

    Los cuatro efectos de la fuente, en su orden:

    1. cancela los movimientos que sirven a esta línea;
    2. **desenlaza** —no cancela— los movimientos destino que fueron creados
       por más de una línea: cancelarlos afectaría a las otras;
    3. si la línea propaga la cancelación, cancela los destinos restantes;
    4. si no, los devuelve a fabricar-contra-existencias y recalcula su estado.

    Devuelve ``None``: ``chain_method`` ejecuta a continuación el ``delete``
    previo, que es el ``return super().unlink()`` de la fuente.
    """
    for move in self.move_ids.all():
        move._action_cancel()

    for move in list(self.move_dest_ids.all()):
        if move.created_purchase_line_ids.count() > 1:
            move.created_purchase_line_ids.remove(self)

    if self.propagate_cancel:
        for move in self.move_dest_ids.all():
            move._action_cancel()
    else:
        for move in self.move_dest_ids.all():
            move.procure_method = move.PROCURE_MAKE_TO_STOCK
            move.save(update_fields=['procure_method', 'updated_at'])
            move._recompute_state()
    return None


def _install_delete(model):
    """``unlink`` de la fuente sobre el ``delete`` de este ORM (D-2)."""
    chain_method(model, 'delete', delete_cancelling_moves)


def apply_purchase_stock_purchase_order_line_extensions():
    """Cuelga sobre ``purchase.PurchaseOrderLine`` lo que ``purchase_stock`` le
    añade — ≙ ``_inherit``."""
    extend_model(
        'purchase', 'PurchaseOrderLine',
        campos={
            'orderpoint': fields.Many2one(
                'stock.StockWarehouseOrderpoint', null=True, blank=True,
                on_delete=models.SET_NULL, db_index=True,
                related_name='purchase_line_ids',
                verbose_name='Regla de reabastecimiento',
                help_text='Punto de pedido que generó esta línea '
                          '(Odoo orderpoint_id).',
            ),
            'location_final': fields.Many2one(
                'stock.StockLocation', null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='purchase_line_ids',
                verbose_name='Ubicación del abastecimiento',
                help_text='Ubicación final que pidió el abastecimiento; puede '
                          'ser más profunda que el destino de la recepción '
                          '(Odoo location_final_id).',
            ),
            'product_description_variants': fields.Char(
                max_length=255, blank=True, default='',
                verbose_name='Descripción personalizada',
                help_text='Descripción que el abastecimiento añade a la línea '
                          '(Odoo product_description_variants).',
            ),
            'propagate_cancel': fields.Boolean(
                default=True, verbose_name='Propagar cancelación',
                help_text='Al cancelar la línea, ¿se cancelan también los '
                          'movimientos que abastece? (Odoo propagate_cancel).',
            ),
        },
        propiedades={'is_storable': is_storable},
        metodos={
            '_get_po_line_moves': _get_po_line_moves,
            '_update_move_date_deadline': _update_move_date_deadline,
            '_check_orderpoint_picking_type': _check_orderpoint_picking_type,
        },
        luego=_install_delete,
    )
