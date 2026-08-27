r"""``stock.replenishment.info`` / ``stock.replenishment.option`` — la pestaña
de proveedores del reabastecimiento: NO PORTADA.

Adaptación de Odoo ``purchase_stock/wizard/stock_replenishment_info.py``
(``odoo19c: addons/purchase_stock/wizard/stock_replenishment_info.py``, 45
líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: la ventana de información de reabastecimiento gana una
pestaña con las tarifas de proveedor del producto, y sólo la muestra cuando el
punto de pedido no tiene ruta o su ruta compra. Y al elegir una ruta desde esa
ventana, si se venía del asistente de reabastecimiento, la elección se le
devuelve a él.

Los 6 símbolos, con su bloqueo medido
======================================

*Métrica:* entradas del cuerpo de las dos clases contadas por AST sobre la
fuente. Con ``_inherit``/``_description`` son 9; descontándolos quedan **6**:
3 campos y 3 métodos (2 en ``StockReplenishmentInfo``, 1 en
``StockReplenishmentOption``).

.. code-block:: text

    grep -rn "stock.replenishment.info"    addons/ src/ --include=*.py  → 8
    grep -rn "stock.replenishment.option"  addons/ src/ --include=*.py  → 0

Los **ocho** hits del primero son todos de ``addons/stock/models/
stock_orderpoint.py`` — su docstring lo declara ausente en ``:162-163``
(*«el modelo transitorio que ``action_stock_replenishment_info`` crea no existe
en este árbol»*) y ``action_stock_replenishment_info`` (``:862-873``) devuelve
un descriptor que lo nombra sin poder instanciarlo. **Cero declaraciones de
clase** para los dos modelos.

Por símbolo:

- ``supplierinfo_id`` (``:11``) — ``related='orderpoint_id.supplier_id'``. El
  campo del otro extremo **sí existe tras este pase**
  (``StockWarehouseOrderpoint.supplier``, ``models/stock.py``); lo que falta es
  el modelo que lo relacionaría.
- ``supplierinfo_ids`` (``:12``) + ``_compute_supplierinfo_ids`` (``:15-18``) —
  las tarifas del producto. La fuente lo declara ``compute`` **con**
  ``store=True``; aquí sería una ``property``, misma divergencia D-1 que
  ``models/purchase_order.py`` ya documenta.
- ``show_vendor_tab`` (``:13``) + ``_compute_show_vendor_tab`` (``:20-27``) —
  su condición (*sin ruta, o ruta que compra*) se apoya en
  ``orderpoint.rule_ids``, que **sí existe**
  (``addons/stock/models/stock_orderpoint.py:403``).
- ``select_route`` (``:33-45``) — devuelve al asistente ``product.replenish``,
  que tampoco está portado (ver ``product_replenish.py`` de este directorio).

Es decir: **la lógica es portable y los datos están; falta el par de modelos
transitorios**. Ninguno de los seis símbolos está bloqueado por una decisión
pendiente — están bloqueados por una clase que nadie ha declarado.

Sucesor
========

El porte de ``stock.replenishment.info`` y ``stock.replenishment.option``
pertenece a ``stock``, y su ausencia ya está registrada allá con la **tarea
#330**. Este archivo es la contraparte de compras: cuando existan, sus 45
líneas se portan con las dos divergencias conocidas del árbol (``compute
store=True`` → ``property``; descriptor de acción sin la URL de Odoo).
"""
