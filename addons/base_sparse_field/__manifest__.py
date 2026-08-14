# Adaptado de Odoo `base_sparse_field/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Campos dispersos',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Campos casi siempre nulos que comparten un único campo '
               'serializado en vez de gastar una columna cada uno.',
    # `depends` idéntico al de la referencia y MEDIDO contra los imports
    # reales: este addon sólo necesita el campo base del ORM.
    'depends': [
        'base',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `base_sparse_field` es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La referencia no declara `auto_install`; se deja explícito en False por
    # el mismo criterio que `base_iban`: aquí la instalación es
    # `INSTALLED_APPS`, no hay mecanismo de auto-instalación por dependencias.
    'auto_install': False,
}
