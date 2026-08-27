r"""``stock.forecasted_product_product`` — el pronóstico con compras en curso:
NO PORTADO.

Adaptación de Odoo ``purchase_stock/report/stock_forecasted.py``
(``odoo19c: addons/purchase_stock/report/stock_forecasted.py``, 38 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: el informe de previsión de existencias muestra lo que
entra y lo que sale. Este archivo le añade **lo que está pedido pero todavía no
confirmado** —las solicitudes de cotización en borrador—, para que el pronóstico
no ignore mercancía que ya se pidió.

Los 2 símbolos, con su bloqueo medido
======================================

*Métrica:* entradas del cuerpo de ``class StockForecasted_Product_Product``
contadas por AST sobre la fuente. Son **3** con ``_inherit``; **2** sin él,
ambos métodos.

.. code-block:: text

    grep -rn "forecasted_product_product"    addons/ src/ --include=*.py  → 0
    grep -rn "def _get_report_header"        addons/ src/ --include=*.py  → 0
    grep -rn "def _add_product_quantities"   addons/ src/ --include=*.py  → 0

``_get_report_header`` (``:10-29``) encadena un ``super()`` inexistente y llama
a ``_add_product_quantities``, que tampoco existe. ``_product_purchase_domain``
(``:31-38``) es sólo el dominio que el primero consume: sin llamador, es código
muerto.

El tercer bloqueo, sobre la línea de compra
=============================================

Aunque el informe existiera, el dominio que la fuente construye lee tres campos
que ``purchase.order.line`` **no tiene** en este árbol: ``state``
(``:12`` — filtra ``draft``/``sent``/``to approve``), ``company_id`` (``:20``) y
``product_uom_qty`` (``:22``). Los tres pertenecen al addon ``purchase``, fuera
del write-set de este pase; están enumerados con los demás en
``models/purchase_order_line.py`` de este addon.

Sucesor
========

El porte del informe de previsión pertenece a ``stock``; el de los tres campos,
a ``purchase``. Este archivo es el puntero que los une para quien retome
cualquiera de los dos.
"""
