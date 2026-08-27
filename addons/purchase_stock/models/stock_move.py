"""``stock.move`` — el movimiento que nació de una línea de compra
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/stock_move.py``
(``odoo19c: addons/purchase_stock/models/stock_move.py``, 252 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade: el enlace en los dos sentidos entre un movimiento de inventario y la
línea de compra que lo originó. ``purchase_line_id`` es «esta recepción viene de
esta línea»; ``created_purchase_line_ids`` es «este movimiento hizo que se
crearan estas líneas» (el caso *make-to-order*: la salida pendiente disparó la
compra). Con ese enlace, el movimiento sabe de dónde salió, quién es el
responsable río arriba y a qué precio se valora.

Porte símbolo por símbolo — 11 de 24
=====================================

*Métrica:* entradas del cuerpo de ``class StockMove`` contadas por AST sobre la
fuente. Son **25** con ``_inherit``; **24** sin él: 2 campos y 22 métodos.
*Ciega a:* lo que otros addons cuelgan sobre ``stock.move``, y a si un método
portado se comporta igual en ejecución — el conteo mide presencia de símbolo,
no conducta (``metrica-decide-la-conclusion.md``).

.. list-table::
   :header-rows: 1
   :widths: 44 14 42

   * - Símbolo (línea)
     - Estado
     - Nota
   * - ``purchase_line_id`` (``:15-17``)
     - portado
     - FK ``SET_NULL``, ``db_index`` (≙ ``index='btree_not_null'``)
   * - ``created_purchase_line_ids`` (``:18-20``)
     - portado
     - M2M, ``db_table`` verbatim de la fuente
   * - ``_prepare_merge_moves_distinct_fields`` (``:22-26``)
     - portado
     - ``combine=extend_list`` — acumula, no releva
   * - ``_prepare_merge_negative_moves_excluded_distinct_fields`` (``:28-30``)
     - portado
     - ídem
   * - ``_get_description`` (``:58-59``)
     - portado
     - relevo por ``None`` de ``chain_method``
   * - ``_should_ignore_pol_price`` (``:95-97``)
     - portado
     - sin ``super()``; símbolo nuevo de este addon
   * - ``_prepare_move_split_vals`` (``:104-110``)
     - portado
     - ``combine`` propio: fusiona los dos diccionarios
   * - ``_clean_merged`` (``:112-114``)
     - portado
     - limpia el M2M tras fusionar
   * - ``_get_source_document`` (``:125-127``)
     - portado
     - la orden de compra gana sobre el albarán
   * - ``_is_purchase_return`` (``:129-135``)
     - portado
     - con la salvedad del XML ID, abajo
   * - ``_get_purchase_line_and_partner_from_chain`` (``:140-151``)
     - portado
     - recorrido BFS verbatim, incluida la ``deque``
   * - ``_compute_packaging_uom_id`` (``:32-37``)
     - **bloqueado**
     - ``grep -rn "def _compute_packaging_uom_id" addons/ src/`` → 0
   * - ``_compute_partner_id`` (``:39-42``)
     - **bloqueado**
     - ídem → 0; y ``_is_dropshipped`` → 0
   * - ``_compute_description_picking`` (``:44-56``)
     - **bloqueado**
     - ``selected_seller_id`` → 0 hits
   * - ``_action_synch_order`` (``:61-93``)
     - **bloqueado**
     - ``to_refund`` → 0, ``purchase_method`` → 0
   * - ``_prepare_extra_move_vals`` (``:99-102``)
     - **bloqueado**
     - ``grep -rn "def _prepare_extra_move_vals"`` → 0
   * - ``_get_upstream_documents_and_responsibles`` (``:116-123``)
     - **bloqueado**
     - la línea de compra no tiene ``state`` ni la orden ``user_id``
   * - ``_get_all_related_sm`` (``:137-138``)
     - **bloqueado**
     - ``grep -rn "def _get_all_related_sm"`` → 0
   * - ``_get_value_from_account_move`` (``:157-215``)
     - **bloqueado**
     - eje de valoración, ver abajo
   * - ``_get_value_from_bill`` (``:217-219``)
     - **bloqueado**
     - ídem
   * - ``_get_quantity_from_bill`` (``:221-223``)
     - **bloqueado**
     - ídem
   * - ``_get_cost_ratio`` (``:225-227``)
     - **bloqueado**
     - ídem
   * - ``_get_value_from_quotation`` (``:229-244``)
     - **bloqueado**
     - ídem
   * - ``_get_related_invoices`` (``:246-252``)
     - **bloqueado**
     - ``invoice_ids`` de la orden no existe

El eje de valoración — un bloqueo, no seis
============================================

Los seis últimos son **una sola pieza ausente vista seis veces**: la factura de
proveedor enlazada a la línea de compra. Medido sobre ``addons/`` + ``src/``:

.. code-block:: text

    grep -rn "invoice_lines"    addons/ src/ --include=*.py  → 0
    grep -rn "_get_valued_qty"  addons/ src/ --include=*.py  → 0
    grep -rn "is_dropship"      addons/ src/ --include=*.py  → 0
    grep -rn "def _get_value_from_account_move" addons/ src/ → 0
    grep -rn "def _get_value_from_quotation"    addons/ src/ → 0

``_get_value_from_account_move`` y ``_get_value_from_quotation`` encadenan un
``super()`` que ``stock_account`` declararía; el ``stock_account`` de este árbol
tiene dos archivos y ninguno toca ``stock.move``. Los otros cuatro son sus
ayudantes: sin el método que los llama son código muerto. Instalarlos sería el
defecto de ``H-API-733``.

Nota sobre ``_is_purchase_return`` — el XML ID que falta
==========================================================

Su segunda rama compara contra ``env.ref('stock.stock_location_inter_company')``.
Ese XML ID **no está sembrado** en este árbol — es la misma ausencia que
``addons/stock/models/stock_replenish_mixin.py`` ya declara y que la tarea
**#330** cubre. El método se porta **con** la rama: cuando la ubicación no se
resuelve, la comparación da ``False`` y queda el primer criterio
(``location_dest.usage == 'supplier'``), que es el caso mayoritario. Se porta
en vez de bloquearse porque el resultado es correcto para ese caso y se vuelve
completo solo cuando la siembra exista.

Nota sobre los dos ``chain_method`` que ACUMULAN
=================================================

``_prepare_merge_moves_distinct_fields`` y su hermano devuelven **listas que se
suman**, no valores que se relevan. Con el relevo por defecto de
``chain_method`` (``result if result is not None else previous(...)``) el puerto
devolvería sólo los dos campos nuevos y **perdería los doce anteriores** — una
fusión de movimientos que ignora ``product`` o ``location``. Por eso van con
``combine=extend_list``, igual que ``account_qr_code_emv`` hizo con
``_get_available_qr_methods`` (``addons/account_qr_code_emv/models/
res_bank.py:523-524``).

``_prepare_move_split_vals`` devuelve un **diccionario**, no una lista, así que
lleva su propio ``combine`` (``_merge_vals``): el ``extend_list`` genérico no
sirve y el relevo perdería todos los valores del ``super()``.
"""
from collections import deque

from django.apps import apps

import fields
import models
from orm.method_chain import chain_method, extend_list
from orm.model_classes import extend_model


def _merge_vals(new, previous):
    """``combine`` para hooks que devuelven un diccionario de valores.

    ≙ el patrón ``vals = super()...; vals['x'] = ...; return vals`` de la
    fuente: lo del ``super()`` primero, lo propio encima. Espeja a
    ``extend_list`` (``orm/method_chain.py:184``), que hace lo mismo con
    listas.
    """
    combined = dict(previous or {})
    combined.update(new or {})
    return combined


# --- métodos portados ------------------------------------------------------

def _prepare_merge_moves_distinct_fields(self, merge_extra=False):
    """≙ ``_prepare_merge_moves_distinct_fields`` (``odoo19c: :22-26``).

    Sólo aporta los dos campos nuevos; ``combine=extend_list`` los suma a los
    que el ``super()`` ya devolvía. La fuente hace ``distinct_fields += [...]``,
    que es exactamente eso.

    Los nombres se dan **sin** el sufijo ``_id``/``_ids`` de la fuente porque
    así se llaman aquí: ``purchase_line`` y ``created_purchase_line_ids``
    (el M2M conserva el plural, el FK no — misma convención que el resto de
    ``StockMove`` en este árbol, donde ``picking_id`` de la fuente es
    ``picking``).
    """
    return ['purchase_line', 'created_purchase_line_ids']


def _prepare_merge_negative_moves_excluded_distinct_fields(self):
    """≙ ``_prepare_merge_negative_moves_excluded_distinct_fields``
    (``odoo19c: :28-30``). También acumula."""
    return ['created_purchase_line_ids']


def _get_description(self):
    """≙ ``_get_description`` (``odoo19c: :58-59``).

    La descripción de la línea de compra manda sobre la del producto. El
    relevo por ``None`` de ``chain_method`` hace el ``else super()`` de la
    fuente: devolver ``None`` cede el turno al método previo.
    """
    if self.purchase_line_id:
        return self.purchase_line.name or None
    return None


def _should_ignore_pol_price(self):
    """≙ ``_should_ignore_pol_price`` (``odoo19c: :95-97``).

    ¿Hay que ignorar el precio de la línea de compra al valorar este
    movimiento? Sí cuando es una devolución, cuando no hay línea de compra, o
    cuando no hay producto.

    ``origin_returned_move_id`` de la fuente es ``origin_returned_move`` aquí
    (``addons/stock/models/stock_move.py``); ``self.product_id.id`` de la
    fuente es la comprobación de que hay producto, que aquí es ``product_id``
    (la columna del FK).
    """
    return bool(self.origin_returned_move_id) or not self.purchase_line_id \
        or not self.product_id


def _prepare_move_split_vals(self, qty, force_split_uom=None):
    """≙ ``_prepare_move_split_vals`` (``odoo19c: :104-110``).

    Al dividir un movimiento, la parte nueva hereda la línea de compra. Si el
    movimiento es *make-to-order* y creó líneas de compra, la parte nueva
    también las hereda — es lo que evita que un pedido pendiente pierda su
    enlace con la compra que lo abastece.

    ``combine=_merge_vals``: la fuente parte del diccionario del ``super()`` y
    le añade estas claves.
    """
    vals = {'purchase_line': self.purchase_line}
    if self.procure_method == self.PROCURE_MAKE_TO_ORDER \
            and self.created_purchase_line_ids.exists():
        vals['created_purchase_line_ids'] = list(
            self.created_purchase_line_ids.all())
    return vals


def _clean_merged(self):
    """≙ ``_clean_merged`` (``odoo19c: :112-114``).

    Tras fusionar, el movimiento absorbido deja de ser el que creó esas líneas
    de compra. ``Command.clear()`` de la fuente es ``.clear()`` del gestor M2M
    de Django.

    Devuelve ``None``, así que ``chain_method`` **también** ejecuta el método
    previo (relevo por ``None``) — que es lo que la fuente consigue con su
    ``super()._clean_merged()`` en la primera línea.
    """
    self.created_purchase_line_ids.clear()
    return None


def _get_source_document(self):
    """≙ ``_get_source_document`` (``odoo19c: :125-127``).

    La orden de compra gana sobre el albarán: ``return
    self.purchase_line_id.order_id or res``. Devolver ``None`` cuando no hay
    línea de compra cede el turno al método previo — el mismo ``or res``.
    """
    if self.purchase_line_id:
        return self.purchase_line.order
    return None


def _is_purchase_return(self):
    """≙ ``_is_purchase_return`` (``odoo19c: :129-135``).

    ¿Este movimiento devuelve mercancía al proveedor? Dos formas: sale hacia
    una ubicación de proveedor, o es la devolución de un movimiento que vino
    de un proveedor (o que va al tránsito entre empresas).

    **Salvedad medida:** ``stock.stock_location_inter_company`` no está
    sembrado en este árbol (tarea #330), así que la comparación contra él da
    ``False`` y sólo queda la rama del ``origin_returned_move`` con origen
    proveedor. Ver el docstring del módulo.
    """
    if self.location_dest_usage == 'supplier':
        return True
    source_move = self.origin_returned_move
    if source_move is None:
        return False
    ir_model_data = apps.get_model('base', 'IrModelData')
    inter_company = ir_model_data.objects.filter(
        module='stock', name='stock_location_inter_company').first()
    if inter_company is not None and self.location_dest_id == inter_company.res_id:
        return True
    return source_move.location_usage == 'supplier'


def _get_purchase_line_and_partner_from_chain(self):
    """≙ ``_get_purchase_line_and_partner_from_chain`` (``odoo19c: :140-151``).

    Asciende por la cadena de movimientos origen —en anchura, con una
    ``deque``, igual que la fuente— hasta encontrar el primero que sí tiene
    línea de compra. Devuelve ``(id de la línea, id del contacto del albarán)``
    o ``(None, None)``.

    El recorrido se porta verbatim, incluido el conjunto ``seen_moves`` que
    impide el ciclo. Lo único que cambia es cómo se lee el conjunto de
    orígenes: ``move.move_orig_ids`` es un gestor de Django, así que se
    materializa con ``.all()``.
    """
    moves_to_check = deque([self])
    seen_moves = set()
    while moves_to_check:
        current_move = moves_to_check.popleft()
        if current_move.purchase_line_id:
            picking = current_move.picking
            return (current_move.purchase_line_id,
                    picking.partner_id if picking is not None else None)
        seen_moves.add(current_move.pk)
        moves_to_check.extend(
            move for move in current_move.move_orig_ids.all()
            if move.pk not in seen_moves
            and all(move.pk != pending.pk for pending in moves_to_check)
        )
    return None, None


def _install_methods(model):
    """Instala los métodos sobre ``stock.StockMove``.

    Escotilla ``luego=`` de ``extend_model`` y no su bloque ``metodos=``: tres
    de estos ocho necesitan un ``combine`` propio, y ``metodos=`` sólo sabe
    instalar el relevo por ``None``. Mismo criterio que
    ``addons/account_qr_code_emv/models/res_bank.py:523``.
    """
    chain_method(model, '_prepare_merge_moves_distinct_fields',
                 _prepare_merge_moves_distinct_fields, combine=extend_list)
    chain_method(model, '_prepare_merge_negative_moves_excluded_distinct_fields',
                 _prepare_merge_negative_moves_excluded_distinct_fields,
                 combine=extend_list)
    chain_method(model, '_prepare_move_split_vals',
                 _prepare_move_split_vals, combine=_merge_vals)
    chain_method(model, '_get_description', _get_description)
    chain_method(model, '_clean_merged', _clean_merged)
    chain_method(model, '_get_source_document', _get_source_document)
    chain_method(model, '_should_ignore_pol_price', _should_ignore_pol_price)
    chain_method(model, '_is_purchase_return', _is_purchase_return)
    chain_method(model, '_get_purchase_line_and_partner_from_chain',
                 _get_purchase_line_and_partner_from_chain)


def apply_purchase_stock_stock_move_extensions():
    """Cuelga sobre ``stock.StockMove`` lo que ``purchase_stock`` le añade —
    ≙ ``_inherit``."""
    extend_model(
        'stock', 'StockMove',
        campos={
            'purchase_line': fields.Many2one(
                'purchase.PurchaseOrderLine', null=True, blank=True,
                on_delete=models.SET_NULL, db_index=True,
                related_name='move_ids',
                help_text='Línea de compra que originó este movimiento '
                          '(Odoo purchase_line_id). El inverso es '
                          '``line.move_ids``.',
            ),
            'created_purchase_line_ids': fields.Many2many(
                'purchase.PurchaseOrderLine', blank=True,
                related_name='move_dest_ids',
                db_table='stock_move_created_purchase_line_rel',
                help_text='Líneas de compra que este movimiento hizo crear '
                          '(Odoo created_purchase_line_ids, caso '
                          'make-to-order). El inverso es '
                          '``line.move_dest_ids``, el nombre que la referencia '
                          'le da a la otra mitad (purchase_order_line.py:30).',
            ),
        },
        luego=_install_methods,
    )
