r"""``purchase.report`` — el análisis de compras por almacén: NO PORTADO.

Adaptación de Odoo ``purchase_stock/report/purchase_report.py``
(``odoo19c: addons/purchase_stock/report/purchase_report.py``, 60 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué hace en la fuente: añade tres columnas al informe de compras —el almacén,
la fecha efectiva de llegada y **los días que tardó**— extendiendo las tres
piezas de la consulta SQL que lo construye (``_select``, ``_from``,
``_group_by``).

Los 6 símbolos, con su bloqueo medido
======================================

*Métrica:* entradas del cuerpo de ``class PurchaseReport`` contadas por AST
sobre la fuente. Son **7** con ``_inherit``; **6** sin él: 3 campos y 3
métodos.
*Ciega a:* nada relevante; el archivo son 60 líneas y se lee entero.

**Bloqueo único, y es la clase entera**:

.. code-block:: text

    grep -rn "purchase.report" addons/ src/ --include=*.py   → 0

El modelo que este archivo extiende **no existe en este árbol**. Lo declara
``purchase`` en la referencia (``odoo19c: addons/purchase/report/
purchase_report.py``) como un modelo con ``_auto = False`` sobre una vista SQL;
el ``purchase`` de este árbol tiene dos archivos —``purchase_order.py`` y
``purchase_order_line.py``— y ningún informe.

Los tres métodos (``_select`` ``:15-30``, ``_from`` ``:32-57``, ``_group_by``
``:59-60``) **sólo existen para extender los del modelo base**: cada uno
inserta su fragmento SQL dentro del que devuelve el ``super()``. Sin ese
``super()`` no hay dónde insertar — es la forma exacta de ``H-API-733``.

Los tres campos (``picking_type_id`` ``:11``, ``effective_date`` ``:12``,
``days_to_arrival`` ``:13``) son **columnas de la vista**, no de una tabla:
``readonly=True`` sobre un modelo ``_auto = False``. Declararlos sin la vista
produciría columnas que ninguna consulta puede leer.

Nota sobre el segundo bloqueo, que persistiría aunque el primero se resolviera
================================================================================

El ``_from`` de la fuente hace ``JOIN stock_move AS move ON
move.purchase_line_id = order_line.id``. Esa columna **sí** existe tras este
pase: la declara ``stock_move.py`` de este addon (``purchase_line``, que Django
materializa como ``purchase_line_id``). Pero el ``_select`` usa además
``l.date_planned`` y ``po.effective_date``:

- ``date_planned`` **no existe** en ``purchase_order_line`` (16 campos ausentes
  enumerados en ``models/purchase_order_line.py`` de este addon);
- ``effective_date`` es una **``property``** en este puerto, no una columna
  (D-1 de ``models/purchase_order.py``), así que SQL no la ve.

Es decir: el informe necesitaría primero que ``purchase`` complete su modelo, y
después que ``effective_date`` se materialice. Se deja escrito para que quien
retome el informe no descubra el segundo bloqueo después de resolver el
primero.

Sucesor
========

El porte del modelo ``purchase.report`` pertenece al addon ``purchase``, no a
éste. Este archivo es su puntero: cuando exista, las 60 líneas de la fuente se
portan sin decisiones nuevas — son tres fragmentos de SQL y tres columnas.
"""
