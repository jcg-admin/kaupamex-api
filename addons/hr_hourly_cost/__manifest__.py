# Adaptado de Odoo `hr_hourly_cost/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': 'Employee Hourly Wage',
    'version': '1.0',
    'category': 'Services/Employee Hourly Cost',
    'summary': 'Employee Hourly Wage',
    # `depends` MEDIDO contra el único import real de este addon
    # (`addons.hr.models.HrEmployee`) — coincide con la referencia, que
    # también declara sólo `hr`.
    'depends': [
        'hr',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
}
