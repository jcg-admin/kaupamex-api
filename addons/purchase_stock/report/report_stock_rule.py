r"""``report.stock.report_stock_rule`` — el diagrama de rutas: NO PORTADO.

Adaptación de Odoo ``purchase_stock/report/report_stock_rule.py``
(``odoo19c: addons/purchase_stock/report/report_stock_rule.py``, 17 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: el informe que dibuja la cadena de reglas de un producto
necesita, para cada regla, una ubicación de origen. Una regla de **compra** no
tiene ninguna —la mercancía viene de fuera—, así que este archivo le pone la
ubicación de proveedores en su lugar. Es una línea de código y un caso
particular real: sin ella el diagrama muestra una flecha que sale de la nada.

El único símbolo, con su bloqueo medido
========================================

*Métrica:* entradas del cuerpo de ``class ReportStockReport_Stock_Rule``
contadas por AST sobre la fuente. Son **2** con ``_inherit``; **1** sin él:
``_get_rule_loc`` (``:10-17``), ningún campo.

.. code-block:: text

    grep -rn "report_stock_rule"  addons/ src/ --include=*.py   → 0
    grep -rn "def _get_rule_loc"  addons/ src/ --include=*.py   → 0

El modelo abstracto que este archivo extiende no existe, y su método tampoco.
El cuerpo portado sería ``res = super()._get_rule_loc(...)`` más una asignación:
**sin el ``super()`` no queda nada**. Es un encadenamiento puro, y el eslabón
base es el que falta (``H-API-733``).

El segundo bloqueo, que persistiría igual
==========================================

La línea que aporta valor es
``res['source'] = self.env.ref('stock.stock_location_suppliers')`` — resuelve un
**XML ID que este árbol no siembra**. Es la misma ausencia que
``addons/stock/models/stock_replenish_mixin.py`` declara para
``stock.stock_location_inter_company`` y que ``models/stock_move.py`` de este
addon vuelve a encontrar: **tarea #330**.

Sucesor
========

El porte del informe ``report.stock.report_stock_rule`` pertenece a ``stock``.
Cuando exista —y cuando la siembra de #330 esté— este archivo son ocho líneas
sin decisiones nuevas.
"""
