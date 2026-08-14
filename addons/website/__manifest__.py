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
    # distancia mide el recorte, no una decisión: el modelo `website`
    # multi-sitio todavía no está portado (DECIDIDO en la tarea #102, el porte
    # es la #103) y lo que hay son cuatro modelos propios pendientes de
    # realinear (#104). No se declara lo que el código no usa.
    #
    # `authz` es el gate de capacidad de las vistas DRF, no dependencia de
    # datos — no se declara (ver lote 2).
    'depends': [
        'base',  # ResCompany — el sitio pertenece a una empresa
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,   # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
