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
    # Seguridad de la fuente
    # (``odoo19c: addons/mass_mailing/__manifest__.py``, clave ``data``),
    # en su orden. Sin los registros cuyo destino no tiene puerto en este
    # árbol, con su sucesor ``mass-mailing-report-models-0397``: el
    # ``user_ids`` del grupo de usuario (``base.user_root`` y
    # ``base.user_admin`` no existen aquí), la regla de
    # ``properties.base.definition`` (filtra por
    # ``mailing.contact.properties``, sin puerto) y las 11 filas del CSV de
    # ``mailing.contact.import``, ``mailing.subscription.optout``,
    # ``mailing.trace.report``, ``link.tracker``, ``mail.blacklist``,
    # ``mail.blacklist.remove``, ``mailing.list.merge``,
    # ``mailing.mailing.test``, ``mailing.contact.to.list``,
    # ``mailing.mailing.schedule.date`` y ``mailing.filter``.
    'data': [
        'data/res_groups_privilege_data.xml',
        'security/res_groups_data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
}
