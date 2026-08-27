r"""``vendor.delay.report`` — la puntualidad del proveedor, por línea de compra:
NO PORTADO.

Adaptación de Odoo ``purchase_stock/report/vendor_delay_report.py``
(``odoo19c: addons/purchase_stock/report/vendor_delay_report.py``, 68 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el **único modelo propio** que ``purchase_stock`` declara — los otros
veinticuatro archivos extienden modelos ajenos. Mide, por línea de compra,
cuánto se pidió y cuánto llegó a tiempo, y de ahí sale el porcentaje de
puntualidad del proveedor.

Los 10 símbolos, y por qué ninguno se declara
===============================================

*Métrica:* entradas del cuerpo de ``class VendorDelayReport`` contadas por AST
sobre la fuente. Son **13**; descontando los tres atributos de clase de modelo
(``_name``, ``_description``, ``_auto``) quedan **10**: 7 campos y 3 métodos.
*Ciega a:* nada relevante; el archivo son 68 líneas y se lee entero.

**No es un modelo con tabla: es una VISTA SQL.** ``_auto = False``
(``odoo19c: :11``) le dice al ORM que no cree la tabla, y ``init()``
(``:21-52``) ejecuta el ``CREATE OR REPLACE VIEW vendor_delay_report AS (…)``
que la define. Sin esa vista, el modelo es una clase que apunta a una relación
inexistente: **toda consulta suya revienta**.

Y la vista **no se puede crear en este árbol**. Su ``SELECT`` lee cinco
columnas de ``purchase_order_line`` y una de ``stock_move_line``; medido contra
los modelos reales:

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Columna que la vista lee
     - ¿Existe?
     - Dónde se midió
   * - ``pol.product_id``
     - **sí**
     - ``addons/purchase/models/purchase_order_line.py:25``
   * - ``m.purchase_line_id``
     - **sí** (este pase)
     - ``models/stock_move.py`` de este addon
   * - ``pol.partner_id``
     - **no**
     - la línea de compra no tiene contacto propio
   * - ``pol.product_uom_qty``
     - **no**
     - sólo existe ``product_qty`` (entero)
   * - ``pol.date_planned``
     - **no**
     - —
   * - ``ml.product_uom_id``
     - **no**
     - ``stock.move.line`` no declara unidad propia aquí

Cuatro de seis ausentes. Un ``CREATE VIEW`` con columnas inexistentes falla al
ejecutarse, así que declarar el modelo ``managed = False`` produciría una clase
registrada, migrable como estado, y **rota en el primer ``objects.all()``** —
una superficie que parece funcionar y no funciona, que es peor que la ausencia
(``porte-completo-no-parcial.md``).

Los tres métodos, uno por uno
===============================

- ``init`` (``:21-52``) — crea la vista. Bloqueado por lo anterior. La
  primitiva que necesita **sí existe**: ``src/tools/sql.py:38`` exporta
  ``drop_view_if_exists``, el mismo nombre que la fuente usa. No es lo que
  falta.
- ``_read_group_select`` (``:54-63``) — el detalle que hace correcto el
  informe: ``on_time_rate`` **no se promedia**, se calcula como
  ``SUM(a_tiempo) / SUM(total) * 100``. Un promedio simple de porcentajes
  pesaría igual una línea de 1 unidad y una de 10 000. Bloqueado: sin la vista
  no hay agrupación que interceptar, y ``_field_to_sql`` no existe en este
  árbol (0 hits).
- ``_read_group`` (``:65-68``) — añade ``HAVING SUM(qty_total) > 0`` para no
  dividir entre cero. Mismo bloqueo.

El campo derivado que la vista NO calcula
===========================================

``on_time_rate`` (``:19``) está declarado como campo pero **el ``SELECT`` de la
vista no lo produce** — sólo ``qty_total`` y ``qty_on_time``. Lo calcula
``_read_group_select`` al agrupar. Es coherente: un porcentaje por línea suelta
no tiene sentido, sólo lo tiene agregado. Se anota porque quien lea el modelo
sin leer el SQL asumiría lo contrario.

Sucesor
========

Este modelo se desbloquea cuando ``purchase`` complete su línea de compra
(``partner_id``, ``product_uom_qty``, ``date_planned``) y ``stock`` su línea de
movimiento (``product_uom_id``). Ninguno de los dos está en el write-set de
este pase; este archivo es el puntero con las cuatro columnas nombradas para
que la medición no haya que rehacerla.
"""
