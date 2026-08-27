# Adaptado de Odoo `hr_timesheet/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': 'Task Logs',
    'version': '1.0',
    'category': 'Services/Timesheets',
    'summary': 'Track employee time on tasks',
    # `depends` MEDIDO contra los imports reales de este addon (task/project/
    # employee/analytic sobre account.analytic.line; hourly_cost sobre
    # employee; project_time_mode_id/timesheet_encode_uom_id de tipo uom.Uom
    # en res.company) — coincide con los cinco de la referencia.
    'depends': [
        'hr',
        'hr_hourly_cost',
        'analytic',
        'project',
        'uom',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
}
