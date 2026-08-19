# Adaptado de Odoo `hr_fleet/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    # `name`/`summary` verbatim de la fuente
    # (odoo19c: hr_fleet/__manifest__.py:4,7).
    'name': 'Fleet History',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Get history of driven cars by employees',
    # `depends` MEDIDO contra los imports reales de este addon — coincide
    # con la referencia (['hr', 'fleet']): los módulos importan
    # addons.hr.models (HrEmployee, HrEmployeePublic, HrDepartureWizard) y
    # addons.fleet.models (FleetVehicle, FleetVehicleAssignationLog,
    # FleetVehicleLogContract, FleetVehicleLogServices,
    # FleetVehicleOdometer). `base` (IrAttachment, ResPartner) llega
    # transitivo por ambos.
    'depends': [
        'hr',     # HrEmployee, HrEmployeePublic, HrDepartureWizard
        'fleet',  # FleetVehicle y sus bitácoras
    ],
    # `data`/`demo`/`assets` de la referencia (security, vistas XML, JS) son
    # capa de cliente Odoo — sin equivalente en este stack (DRF headless).
    # Licencia de la fuente, tal como su manifest la declara (DEC-KX-03
    # punto 1): `hr_fleet` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # `auto_install: True` en la referencia (se activa con hr + fleet). Aquí
    # el alta la deriva el grafo de manifiestos (LOCAL_APPS).
    'auto_install': False,
    'author': 'Odoo S.A.',
}
