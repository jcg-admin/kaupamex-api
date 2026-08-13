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
        'base',      # TimeStampedModel, ResPartner, ResUsers, ResCompany,
                     # ResCurrency (via company), SystemParameter
        'mail',      # MailThread (chatter + activity_ids/activity_schedule)
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `fleet` en Odoo Community es
    # LGPL-3.
    'license': 'LGPL-3',
    'application': False,  # corte parcial, no el módulo completo
    'installable': True,
    'auto_install': False,
}
