"""``timesheets.analysis.report`` — el informe de horas, con su columna de
ingreso y margen (Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/report/timesheets_analysis_report.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 57 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``TimesheetsAnalysisReport``,
``_inherit``), **8 campos**, **3 métodos** (uno de ellos, ``_table_query``,
declarado como ``property``). **No-op medido** — 0 de 11 portados, y la razón
es de SITIO, no de mecanismo.

Por qué este archivo no declara ningún modelo
================================================

El modelo base **no existe en este árbol**: ``timesheets.analysis.report`` lo
declara ``hr_timesheet``
(``odoo19c: addons/hr_timesheet/report/timesheets_analysis_report.py``), cuyo
puerto aquí (``api@5ae7798``) no incluye directorio ``report/`` — medido:
``ls addons/hr_timesheet/`` da ``models/`` y ``wizard/``, y 0 hits de
``TimesheetsAnalysisReport`` en ``addons/`` y ``src/``.

``sale_timesheet`` sólo **extiende** ese informe: le añade ocho columnas
(``order_id``, ``so_line``, ``timesheet_invoice_type``,
``timesheet_invoice_id``, ``timesheet_revenues``, ``margin``,
``billable_time``, ``non_billable_time``) y reescribe su ``_select``/``_from``
para que el ``_table_query`` las produzca.

**Declarar aquí el modelo entero sería ponerlo en el hogar equivocado** — el
defecto que ``H-API-568`` (símbolo del núcleo aterrizado en un addon) y
``H-API-578`` (archivo en una raíz que la referencia no tiene) ya registran.
La instrucción general de esta tanda —*"los reportes SQL de la fuente
(``_auto=False`` / ``_table_query``) se declaran como modelo con
``managed=False``"*— gobierna el caso en que el informe **es de este addon**;
aquí es de ``hr_timesheet``, y este archivo es su extensión.

Sucesor: tarea PENDIENTE DE ASIGNAR — portar
``hr_timesheet/report/timesheets_analysis_report.py`` como modelo
``managed=False`` en ``addons/hr_timesheet/report/``, con su vista SQL creada
por migración (precedente exacto en este árbol:
``api: addons/hr/models/hr_employee_public.py:214``, ``Meta.managed = False``
+ vista creada por migración). Cuando aterrice, este archivo cuelga sus ocho
columnas y sus dos fragmentos de SQL.

Segundo bloqueador, independiente del primero
================================================

Aunque el informe base existiera hoy, cuatro de las ocho columnas y los dos
fragmentos de SQL leen tablas que este árbol no tiene:

- ``so_line`` y ``order_id`` → ``sale.order.line``/``sale.order`` **sí**
  existen, pero la columna ``so_line`` sobre el apunte no
  (``odoo19c: sale/models/analytic.py:9``; ver el bloqueo raíz en
  ``models/hr_timesheet.py``);
- ``_select`` (:33-47) hace ``JOIN`` contra ``sale_order_line`` leyendo
  ``price_subtotal``, ``product_uom_id`` y ``product_id``, y contra
  ``product_template`` leyendo ``service_type`` e ``invoice_policy``: de esos
  cinco, **ninguno** existe en este árbol (medido: ``sale.SaleOrderLine``
  declara nueve campos y ninguno es ésos; ``service_type``/``invoice_policy``
  dan 0 hits).

Porte símbolo por símbolo — 0 de 11
======================================

Los ocho campos (:11-18) y los tres métodos —``_table_query`` (:21-29),
``_select`` (:31-47), ``_from`` (:49-57)— comparten los dos bloqueadores de
arriba y **el mismo** sucesor. No se listan uno a uno porque su desenlace es
idéntico y una tabla de once filas iguales oculta que el bloqueo es único.
"""


def apply_sale_timesheet_timesheets_analysis_report_extensions():
    """No-op declarado — el informe base no existe en este árbol. Ver el
    docstring del módulo.

    Se conserva la función (y su entrada en
    ``SaleTimesheetConfig._EXTENSIONES``) porque es el punto exacto donde se
    cuelgan las ocho columnas el día que ``hr_timesheet`` porte su informe.
    """
    return None


__all__ = ['apply_sale_timesheet_timesheets_analysis_report_extensions']
