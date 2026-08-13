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
        'base',        # ResPartner, ResUsers, ResCompany
        'mail',        # MailThread — el hilo de seguimiento
        'sales_team',  # CrmTeam — el equipo al que se asigna
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
