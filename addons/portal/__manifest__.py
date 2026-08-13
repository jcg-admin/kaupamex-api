# Adaptado de Odoo Community `portal/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Portal',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': 'Separación backoffice / cliente: compartición de documentos '
               'por token y campos editables del cliente',
    # La referencia declara ['web', 'html_editor', 'http_routing', 'mail',
    # 'auth_signup']. `web`/`html_editor`/`http_routing` son la capa QWeb/
    # frontend de Odoo (páginas del portal, pager, chatter) que este árbol NO
    # porta — el SPA React es el frontend. Las depends REALES del núcleo
    # Python portado (medidas contra los imports):
    #   base        — res.partner, res.users (eje is_public/is_internal)
    #   authz_signup — la política de alta federada del enlace de compartición
    #   authz       — la capacidad que gatea la gestión de accesos
    'depends': [
        'authz',
        'authz_signup',
        'base',
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
