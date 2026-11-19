# Adaptado de Odoo Community `fleet/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Flota (núcleo: vehículos, modelos y bitácoras)',
    'version': '1.0',
    'category': 'Human Resources/Fleet',
    'summary': (
        'fleet.vehicle + catálogo (modelo/marca/categoría/etiqueta/estado) + '
        'bitácoras (odómetro/contrato/servicio/asignación) — sin reportes ni '
        'wizard de correo (cierre parcial)'
    ),
    # `depends` MEDIDO contra los imports reales de los 11 modelos portados,
    # no copiado de la referencia (que declara sólo base+mail: aquí se suma
    # `hr`? — no: fleet no importa nada de hr; company/currency/partner/users
    # viven en `base`).
    'depends': [
        'base',  # TimeStampedModel, ResPartner, ResUsers, ResCompany,
        # ResCurrency (via company), SystemParameter
        'mail',  # MailThread (chatter + activity_ids/activity_schedule)
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `fleet` en Odoo Community es
    # LGPL-3.
    'license': 'LGPL-3',
    'application': False,  # corte parcial, no el módulo completo
    # Seguridad de la fuente
    # (``odoo19c: addons/fleet/__manifest__.py:31-33``), en su orden: copia
    # fiel, sin ``fleet_group_manager.user_ids`` (``base.user_root`` y
    # ``base.user_admin`` no existen aquí, como en ``purchase``) y sin los
    # registros de los modelos que este árbol no porta
    # (``fleet.vehicle.cost.report``, ``fleet.vehicle.odometer.report`` y
    # ``fleet.vehicle.send.mail``: tres filas del CSV y la regla
    # ``ir_rule_fleet_report``). Vuelven con ``fleet-report-models-0397``.
    'data': [
        'security/fleet_security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
}
