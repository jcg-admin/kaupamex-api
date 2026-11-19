# Adaptado de Odoo Community `crm/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'CRM',
    'version': '1.0',
    'category': 'Sales/CRM',
    'summary': (
        'CrmLead y su etapa, la conversión de iniciativa a oportunidad y la '
        'captura de contacto desde el sitio'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara ['base_setup',
    # 'sales_team', 'mail', 'resource', 'digest'] más cinco que este árbol no
    # tiene. `resource` (el calendario del comercial) y `digest` (el resumen)
    # no se miden: el segundo consume, no provee.
    #
    # `authz` es el gate de capacidad, no dependencia de datos (ver lote 2).
    'depends': [
        'base',  # ResPartner, ResUsers, ResCompany
        'mail',  # MailThread — el hilo de seguimiento
        'sales_team',  # CrmTeam — el equipo al que se asigna
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,
    # Seguridad de la fuente
    # (``odoo19c: addons/crm/__manifest__.py``, clave ``data``), en su orden.
    # Sin los registros cuyo destino no tiene puerto en este árbol, con su
    # sucesor ``crm-report-models-0397``: del XML, el menú
    # ``contacts.res_partner_menu_config`` (``contacts`` no está), las tres
    # reglas de ``crm.activity.report`` y las dos de ``mail.activity.plan``;
    # del CSV, las filas de ``calendar.event``, ``calendar.event.type``,
    # ``mail.activity.plan``, ``mail.activity.plan.template``,
    # ``crm.activity.report`` y los asistentes ``crm.lead.lost``,
    # ``crm.lead.pls.update``, ``crm.merge.opportunity`` y
    # ``crm.lead2opportunity.partner`` (las dos variantes).
    'data': [
        'security/crm_security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
}
