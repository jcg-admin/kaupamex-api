# Adaptado de Odoo Community `mass_mailing/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Correo masivo',
    'version': '1.0',
    'category': 'Marketing/Email Marketing',
    'summary': (
        'La campaña de correo, su lista de contactos, la baja del '
        'suscriptor y las métricas de entrega'
    ),
    # `depends` MEDIDO da tres; la referencia declara ['mail', 'digest'] más
    # cinco que este árbol no tiene (`contacts`, `html_builder`, `utm`,
    # `link_tracker`, `social_media`). `digest` no se mide: el resumen
    # periódico consume las métricas de campaña, no al revés.
    #
    # `authz` es el gate de capacidad, no dependencia de datos (ver lote 2).
    'depends': [
        'base',  # ResPartner, ResCompany
        'mail',  # MailTemplate y la cola de envío
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
