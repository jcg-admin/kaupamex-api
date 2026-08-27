# Adaptado de Odoo `sale_timesheet/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': 'Sales Timesheet',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': 'Sell based on timesheets',
    'description': """
Allows to sell timesheets in your sales order
=============================================

This module set the right product on all timesheet lines
according to the order/contract you work on. This allows to
have real delivered quantities in sales orders.
""",
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia (que declara sólo ['sale_project', 'hr_timesheet']).
    #
    #   base          ResCurrency, TimeStampedModel
    #                 (models/project_sale_line_employee_map.py)
    #   hr            HrEmployee                    (ídem)
    #   project       Project                       (ídem)
    #   sale          SaleOrder, SaleOrderLine      (ídem + models/hr_timesheet.py)
    #   analytic      AccountAnalyticLine           (5 archivos)
    #   account       AccountMove (models/hr_timesheet.py) y
    #                 AccountMoveReversal (models/account_move_reversal.py)
    #   product       ProductProduct, ProductTemplate
    #   hr_timesheet  NO se importa un símbolo, pero SÍ se encadena el
    #                 `_hourly_cost` que instala, y se leen tres columnas que
    #                 cuelga (Project.allow_timesheets,
    #                 ResCompany.project_time_mode_id / timesheet_encode_uom_id).
    #                 Es una dependencia de ORDEN, y el grafo es quien la
    #                 garantiza: sin ella el encadenado instalaría el nuestro
    #                 sin anterior y perdería el fallback al hourly_cost del
    #                 empleado — en silencio.
    #
    # `uom` NO se declara: no se importa ningún símbolo suyo; las unidades
    # llegan como objetos ya resueltos desde `res.company`, y `hr_timesheet`
    # (que sí lo declara) va antes en el grafo.
    #
    # `sale_project` — la referencia lo declara y aquí NO, por el mismo
    # criterio con que `project_account` retiró `account` de su depends: nada
    # de este addon lo importa. Su superficie es exactamente la lista de
    # bloqueadores del docstring de `__init__.py` (allow_billable,
    # sale_line_id, service_policy, service_type); vuelve al depends el día que
    # esos campos aterricen y sus consumidores se desbloqueen.
    'depends': [
        'base',
        'hr',
        'project',
        'sale',
        'analytic',
        'account',
        'product',
        'hr_timesheet',
    ],
    # `data` (14 XML de vistas + seguridad) y `demo` no se portan: cliente web
    # de Odoo, criterio ya establecido en el árbol (hr_timesheet, sale_project,
    # project_account). La ÚNICA pieza de `data` con consecuencia funcional es
    # el producto semilla `sale_timesheet.time_product`
    # (data/sale_service_data.xml) — su ausencia está declarada como bloqueo en
    # models/product_product.py, models/product_template.py y
    # models/project_project.py, y su porte es data, no esquema (precedente de
    # forma: addons/account_fleet/data/fleet_service_types.py).
    #
    # `post_init_hook` / `uninstall_hook` de la referencia tampoco se portan:
    # son ganchos del instalador de módulos de Odoo y operan sobre campos
    # ausentes (service_type, invoice_policy) e `ir.rule`. Ver el docstring de
    # `__init__.py`.
    'auto_install': True,
    'author': 'Odoo S.A.',
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
}
