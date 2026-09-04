"""``stock.move`` — la bandera que decide si una devolución se reembolsa
(Odoo ``stock_account``).

Adaptación de Odoo ``stock_account/models/stock_move.py``
(``odoo19c: addons/stock_account/models/stock_move.py``, 710 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué añade en este pase: ``to_refund``. Es la bandera que distingue una
devolución que **corrige la cantidad recibida en la orden de compra** de una
que no la toca. Sin ella, un consumidor que devuelve mercancía no puede saber
si la línea de compra debe bajar su cantidad recibida — que es exactamente lo
que ``PurchaseOrderLine._get_outgoing_incoming_moves`` pregunta.

Porte símbolo por símbolo — 1 de 68, y los 67 restantes tienen sucesor
=======================================================================

*Métrica:* entradas del cuerpo de ``class StockMove`` contadas por AST sobre la
fuente, descontando ``_inherit``: **16 campos** y **52 métodos**.
*Ciega a:* si el campo portado se comporta igual en ejecución — el conteo mide
presencia de símbolo, no conducta (``metrica-decide-la-conclusion.md``).

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Símbolo (línea)
     - Estado
   * - ``to_refund`` (``:20-22``)
     - **portado** — mismo nombre, mismo ``default=True``, mismo ``copy=True``,
       misma ayuda
   * - Los otros 15 campos y los 52 métodos
     - **NO portados**, y no por bloqueo: son el **motor de valoración** entero
       (``value``, ``remaining_qty``, ``_create_account_move``, ``_set_value``,
       ``_get_value_data``…). Su alcance es una iniciativa, no un paso de este
       barrido. Sucesor ya registrado: tarea **#151**

Por qué ``to_refund`` se porta ahora y sola
--------------------------------------------

Porque **ya tiene dos consumidores medidos en este árbol**, y uno de ellos la
escribe:

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Sitio
     - Qué hace
   * - ``addons/stock/models/stock_rule.py:936``
     - ``values['to_refund'] = True`` — la **escribe** al preparar el
       movimiento de una devolución
   * - ``addons/purchase_stock/models/purchase_order_line.py``
     - ``_get_outgoing_incoming_moves`` la **lee** en sus dos ramas

La escritura ya existía sobre un campo que no existía: el valor se pasaba a un
``dict`` y se perdía al construir el movimiento. Portar la columna es lo que
hace que esa escritura tenga receptor.

El sitio del archivo se leyó contra la referencia
--------------------------------------------------

``atributos-de-clase-de-modelo.md``, segunda cláusula: antes de crear un archivo
en una raíz espejada se lista la raíz de la referencia.
``odoo19c: addons/stock_account/models/`` declara ``stock_move.py``; este árbol
tenía sólo ``product_costing.py`` y ``stock_valuation_layer.py``. El campo va
aquí y no en ``addons/stock``, porque es la referencia quien decide de qué addon
cuelga cada extensión — ``stock`` no conoce el reembolso.

Divergencia declarada
======================

**D-1 — la extensión se aplica en ``ready()``, no al importar el paquete.**
Colgar un campo sobre ``stock.StockMove`` en tiempo de import falla con
``AppRegistryNotReady``. Mismo patrón que ``PurchaseStockConfig``: el
``importlib.import_module`` de ``StockAccountConfig.ready()`` es la **excepción
número 4** de ``no-lazy-imports.md`` — una llamada de función, no un statement
``import``.
"""
import fields
from orm.model_classes import extend_model


def apply_stock_account_stock_move_extensions():
    """Cuelga sobre ``stock.StockMove`` lo que ``stock_account`` le añade —
    ≙ ``_inherit``."""
    extend_model(
        'stock', 'StockMove',
        campos={
            'to_refund': fields.Boolean(
                'Update quantities on SO/PO', default=True, copy=True,
                help_text='Dispara la disminución de la cantidad '
                          'entregada/recibida en la orden de venta o compra '
                          'asociada (Odoo to_refund).',
            ),
        },
    )
