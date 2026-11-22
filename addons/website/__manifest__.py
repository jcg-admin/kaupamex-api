# Adaptado de Odoo Community `website/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Sitio web',
    'version': '1.0',
    'category': 'Website/Website',
    'summary': (
        'El sitio como registro: dominio, empresa, menú público y las '
        'páginas que el frontend consume'
    ),
    # `depends` MEDIDO da sólo ['authz', 'base'] contra los cinco presentes de
    # la referencia (['digest', 'web', 'portal', 'authz_signup', 'mail']). La
    # distancia mide el recorte, no una decisión. El modelo `website` ya está
    # portado (`models/website.py`); lo que falta de la fuente son sus
    # dependencias de datos, no el modelo. No se declara lo que el código no
    # usa.
    #
    # `authz` es el gate de capacidad de las vistas DRF, no dependencia de
    # datos — no se declara (ver lote 2).
    'depends': [
        'base',  # ResCompany — el sitio pertenece a una empresa
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    # Seguridad de la fuente (`odoo19c: addons/website/__manifest__.py:31-34`):
    # primero el XML de grupos, después el CSV que los nombra.
    'data': [
        'security/website_security.xml',
        'security/ir.model.access.csv',
    ],
    'application': True,  # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
