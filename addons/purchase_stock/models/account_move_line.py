r"""``account.move.line`` — la diferencia de precio de la factura de proveedor:
NO PORTADA.

Adaptación de Odoo ``purchase_stock/models/account_move_line.py``
(``odoo19c: addons/purchase_stock/models/account_move_line.py``, 33 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este archivo existe **sin código**, y las dos ausencias están medidas, no
supuestas. Ninguno de los dos métodos de la fuente tiene aquí un solo símbolo
sobre el que operar.

Los 2 símbolos de la fuente, con su bloqueo medido
====================================================

*Métrica:* entradas del cuerpo de ``class AccountMoveLine`` contadas por AST
sobre la fuente. Son **3** con ``_inherit``; **2** sin él, ambos métodos, cero
campos.
*Ciega a:* lo que ``purchase`` (no este addon) le cuelga a ``account.move.line``
— en particular ``purchase_line_id``, que este archivo consume pero no declara.

``_get_price_unit_val_dif_and_relevant_qty`` (``odoo19c: :12-30``)
--------------------------------------------------------------------

Calcula la diferencia entre el precio facturado y el precio de valoración de la
línea. **Bloqueado por cinco piezas ausentes**, las cinco greppeadas en este
pase sobre ``addons/`` + ``src/``:

.. code-block:: text

    grep -rn "_get_gross_unit_price"  addons/ src/ --include=*.py   → 0
    grep -rn "purchase_line_id"       addons/ src/ --include=*.py   → 1
        (y el único hit es una CITA en prosa dentro de
         addons/sale_purchase/models/sale_line_purchase_link.py:4,
         no una declaración de campo)

Y sobre el propio ``AccountMoveLine`` de este árbol
(``addons/account/models/account_move_line.py``), cuyo cuerpo entero son 13
campos: ``product_id``, ``product_uom_id``, ``company_id``, ``date``,
``company_currency_id`` y ``analytic_distribution`` **no están entre ellos**.
El método necesita los seis a la vez.

Su desenlace es **bloqueado por el porte de la factura de proveedor**: cuando
``account.move.line`` tenga producto, unidad, empresa y fecha, y ``purchase``
haya colgado ``purchase_line_id``, este método se porta tal cual — su cuerpo no
tiene nada específico de este stack.

``_get_stock_moves`` (``odoo19c: :32-33``)
--------------------------------------------

Una sola línea: ``return super()._get_stock_moves() | self.purchase_line_id.move_ids``.
Es un **encadenamiento puro**: no aporta lógica, sólo suma los movimientos de la
línea de compra a los que el ``super()`` ya devolvía.

**Bloqueado por la ausencia del eslabón anterior.** Medido:

.. code-block:: text

    grep -rn "def _get_stock_moves" addons/ src/ --include=*.py     → 0

El ``super()`` que encadena lo declara ``stock_account`` en la referencia
(``odoo19c: addons/stock_account/models/account_move_line.py``), y el
``stock_account`` de este árbol tiene **dos** archivos —``product_costing.py``
y ``stock_valuation_layer.py``— ninguno de los cuales toca
``account.move.line``. Instalar aquí el primer eslabón de una cadena cuyo
eslabón base no existe es exactamente lo que ``H-API-733`` registra: un stub
con premisa falsa que sepulta la implementación real cuando llegue.

Por qué NO se cuelga ``purchase_line_id`` desde aquí
======================================================

Porque **no es de este addon**. La referencia lo declara en
``odoo19c: addons/purchase/models/account_move_line.py`` — el addon
``purchase``, que en este árbol existe y no lo tiene. Colgarlo desde
``purchase_stock`` pondría el campo en el módulo equivocado y haría que el día
que ``purchase`` lo porte aparecieran dos columnas para el mismo dato
(``add_field_if_absent`` evitaría la segunda, pero el orden de carga decidiría
cuál gana — un no-determinismo silencioso).

Hallazgo derivado, con file:line
==================================

``addons/account/models/account_move_line.py`` declara ``quantity`` y
``price_unit`` pero **no** ``product``: una línea de asiento sin producto no
puede valorarse contra el costo estándar del producto, que es el eje entero de
este archivo de la referencia. No es deuda de este puerto — se registra para
que quien porte la factura de proveedor lo encuentre medido.
"""
