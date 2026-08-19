r"""``stock_account.stock.valuation.report`` — mercancía recibida y no
facturada: NO PORTADO.

Adaptación de Odoo ``purchase_stock/report/stock_valuation_report.py``
(``odoo19c: addons/purchase_stock/report/stock_valuation_report.py``, 40
líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: valora, orden de compra por orden de compra, lo que ya
entró al almacén y el proveedor todavía no ha facturado. Es una partida real de
balance —*goods received not invoiced*—, no un informe cosmético.

El único símbolo, con su bloqueo medido
========================================

*Métrica:* entradas del cuerpo de ``class StockValuationReport`` contadas por
AST sobre la fuente. Son **2** con ``_inherit``; **1** sin él:
``_compute_goods_received_not_invoiced`` (``:8-40``), ningún campo.

.. code-block:: text

    grep -rn "stock.valuation.report"  addons/ src/ --include=*.py   → 0
    grep -rn "invoice_lines"           addons/ src/ --include=*.py   → 0

Dos ausencias, no una: el modelo abstracto que se extiende, y —dentro del
método— el enlace ``purchase.order.line.invoice_lines`` del que sale el valor ya
facturado. A ellas se suman tres campos de la línea de compra que este árbol no
declara: ``qty_to_invoice`` (``:11``), ``date_approve`` (``:15``) y
``price_subtotal`` (``:30``).

Hallazgo sobre la propia referencia
=====================================

**Este archivo NO se importa en ``report/__init__.py`` de la fuente.** Medido
sobre ``odoo19c: addons/purchase_stock/report/__init__.py`` (6 líneas): importa
``purchase_report``, ``report_stock_rule``, ``stock_forecasted`` y
``vendor_delay_report`` — **cuatro de los cinco** ``.py`` del directorio.

No se afirma por qué. El archivo lleva un ``# TODO remove in master`` en su
línea 7, lo que es coherente con un símbolo en retirada, pero eso es una
lectura, no una medición. Se registra como hallazgo del árbol de referencia
para que quien lo retome sepa que **en la fuente tampoco se carga**.

Consecuencia para este puerto: el archivo se espeja —el sitio se lee contra la
referencia, ``atributos-de-clase-de-modelo.md`` segunda cláusula— y, como allá,
**no se importa** desde ``report/__init__.py``.
"""
