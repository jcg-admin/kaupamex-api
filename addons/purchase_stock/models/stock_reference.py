"""``stock.reference`` — las compras que comparten un encargo
(Odoo ``purchase_stock``).

Adaptación de Odoo ``purchase_stock/models/stock_reference.py``
(``odoo19c: addons/purchase_stock/models/stock_reference.py``, 9 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 1
====================================

*Métrica:* entradas del cuerpo de ``class StockReference`` contadas por AST
sobre la fuente. Son **2** con ``_inherit``; **1** sin él — el campo
``purchase_ids``. Cero métodos.
*Ciega a:* lo que otros addons cuelgan sobre ``stock.reference`` (``sale_stock``
le cuelga ``sale_ids`` en la referencia) — este conteo mira un solo archivo.

=================================================  ===========================
Símbolo de la referencia                           Dónde queda en este puerto
=================================================  ===========================
``StockReference.purchase_ids`` (``:7-9``)         campo homónimo (M2M)
=================================================  ===========================

Los cuatro argumentos posicionales de la fuente
================================================

La firma de la referencia es::

    purchase_ids = fields.Many2many(
        'purchase.order', 'stock_reference_purchase_rel', 'reference_id',
        'purchase_id', string="Purchases", copy=False)

- ``'purchase.order'`` → ``'purchase.PurchaseOrder'`` (el par de Django del
  modelo ya portado en ``addons/purchase/models/purchase_order.py``).
- ``'stock_reference_purchase_rel'`` → ``db_table`` **verbatim**: el nombre de
  la tabla intermedia se conserva, igual que hizo ``stock`` con
  ``stock_reference_move_rel``.
- ``'reference_id'`` / ``'purchase_id'`` — los nombres de las dos columnas de
  la tabla intermedia. **Divergencia de mecanismo declarada:** Django los
  deriva del nombre del modelo (``stockreference_id`` / ``purchaseorder_id``)
  y no admite fijarlos sin un ``through`` explícito. Un ``through`` propio
  costaría un modelo intermedio entero para renombrar dos columnas; se
  conserva el nombre de la TABLA, que es lo que un dump o una consulta cruda
  busca primero.
- ``copy=False`` — **BLOQUEADO por la ausencia de ``copy_data``**. Greppeado:
  ``grep -rn "copy=False" src/orm/fields*.py`` → 0 hits; ningún ``Field`` de
  este ORM acepta ``copy=`` como kwarg. El mecanismo que lo lee allá es
  ``copy_data`` (duplicar un registro), que aquí existe sólo en modelos
  concretos que lo escriben a mano (``stock.StockWarehouse.copy_data``), no
  como motor genérico. Sucesor: el porte de ``copy_data`` genérico; sin él la
  bandera no tiene consumidor.
"""
from orm.model_classes import extend_model

import fields


def apply_purchase_stock_stock_reference_extensions():
    """Cuelga ``purchase_ids`` sobre ``stock.StockReference`` — ≙ ``_inherit``.

    ``related_name='reference_ids'`` conserva el nombre que la referencia le
    da a la otra mitad: allá ``purchase.order`` no declara el inverso en este
    archivo, pero ``PurchaseOrder._add_reference``/``_remove_reference``
    (``odoo19c: purchase_stock/models/purchase_order.py:436-444``) lo lee como
    ``order.reference_ids`` — el mismo nombre que ``stock.move`` ya usa.
    """
    extend_model(
        'stock', 'StockReference',
        campos={
            'purchase_ids': fields.Many2many(
                'purchase.PurchaseOrder', blank=True,
                related_name='reference_ids',
                db_table='stock_reference_purchase_rel',
                help_text='Órdenes de compra que comparten esta referencia '
                          '(Odoo purchase_ids). El inverso es '
                          '``order.reference_ids``.',
            ),
        },
    )
