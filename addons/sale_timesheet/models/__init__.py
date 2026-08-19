"""Modelos del addon ``sale_timesheet`` (estructura Odoo: un archivo por
módulo — 13 de los 13 de la referencia, cada uno con desenlace declarado).

**Sólo importa el modelo propio** (``ProjectSaleLineEmployeeMap``) — mismo
criterio que ``addons.hr_timesheet.models`` / ``addons.account_fleet.models``:
los otros doce archivos cuelgan extensiones sobre modelos AJENOS
(``analytic.AccountAnalyticLine``, ``project.Project``,
``project.ProjectTask``, ``sale.SaleOrder``, ``sale.SaleOrderLine``,
``account.AccountMove``, ``account.AccountMoveLine``,
``account.move.reversal``, ``product.ProductTemplate``,
``product.ProductProduct``, ``hr.HrEmployee``, ``res.config.settings``) y los
cuelga ``SaleTimesheetConfig.ready()``, no este paquete — en tiempo de import
del paquete el registro de modelos aún no está poblado.

Reparto medido de los trece
==============================

- **5 cuelgan símbolos reales:** ``hr_timesheet.py`` (4 columnas + 2
  properties + 4 métodos sobre el apunte), ``project_project.py`` (2 columnas
  + 2 properties + 6 hooks), ``project_task.py`` (3 properties),
  ``sale_order.py`` (3 properties), ``sale_order_line.py`` (1 columna + 1
  hook), ``account_move.py`` (3 properties + 1 hook),
  ``account_move_reversal.py`` (1 método encadenado) y ``product_template.py``
  (1 columna + 1 hook) — ocho, contando los que cuelgan al menos un símbolo.
- **1 declara el modelo propio:** ``project_sale_line_employee_map.py``.
- **4 son no-op declarado:** ``account_move_line.py``, ``hr_employee.py``,
  ``product_product.py``, ``res_config_settings.py``.

El bloqueo de mayor alcance del addon está documentado en
``hr_timesheet.py``: ``so_line`` sobre ``account.analytic.line`` lo declara
``sale`` (``odoo19c: sale/models/analytic.py:9``) y no existe en este árbol.
Un ``grep so_line`` sobre este directorio recupera el conjunto entero de
símbolos que arrastra.
"""
from .project_sale_line_employee_map import ProjectSaleLineEmployeeMap

__all__ = ['ProjectSaleLineEmployeeMap']
