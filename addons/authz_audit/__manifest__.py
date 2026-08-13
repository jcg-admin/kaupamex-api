# Forma propia: la referencia no tiene un addon de bitácora de autorización —
# su rastro de acceso vive en el log del servidor, no en un modelo.
{
    'name': 'Bitácora de autorización',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'AuthzEvent: registro append-only de concesión, revocación y '
        'elevación de sesión, para auditar quién pudo qué y cuándo'
    ),
    # `depends` MEDIDO contra los imports reales (`models.py:11`), no copiado:
    # no hay referencia de la que copiar. Un solo destino, y es la raíz.
    'depends': [
        'base',  # ResUsers, ResCompany, AppendOnlyModel
    ],
    # Eje propio: sin licencia heredada que declarar (DEC-KX-03).
    'license': 'propio',
    'application': False,
    'installable': True,
    'auto_install': False,
}
