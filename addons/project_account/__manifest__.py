# Adaptado de Odoo `project_account/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': "Project - Account",
    'summary': "project profitability items computation",
    'description': """
Allows the computation of some section for the project profitability
==================================================================================================
This module allows the computation of the 'Vendor Bills', 'Other Costs' and 'Other Revenues' section for the project profitability, in the project update view.
""",
    'category': 'Accounting/Accounting',
    # `depends` MEDIDO contra el destino real de extensión de este pase:
    # sólo `project.Project` recibe símbolos (los dos hooks del panel de
    # rentabilidad). La referencia declara ['account', 'project']; `account`
    # vuelve al depends cuando se desbloqueen sus consumidores — los cinco
    # métodos con arista declarada en models/project_project.py (todos
    # cuelgan de `Project.account_id` / `AccountMoveLine.
    # analytic_distribution`, ausentes hoy).
    'depends': ['project'],
    # `data` (4 XML de vistas) no se porta: cliente web de Odoo, criterio ya
    # establecido en el árbol (hr_timesheet, sale_project).
    'auto_install': True,
    'author': 'Odoo S.A.',
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
}
