# Forma propia: la referencia no tiene un addon de observabilidad — su
# instrumentación vive dispersa en el servidor (`odoo/service/`, el logger
# de `http.py`), no como modelo consultable.
{
    'name': 'Observabilidad',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'BusinessEvent: el hecho de dominio consultable para el operador L0. '
        'RequestLog se retiró con DEC-AF-11'
    ),
    # `depends` MEDIDO daba ['authz', 'base']; la arista a `authz` era el gate
    # de capacidad de `AdminLogsView`, que DEC-AF-11 mudó a `base` junto con
    # el modelo que servía. Hoy la medición da sólo `base`, así que el par que
    # H-API-562 registraba dentro del ciclo ya no existe por este addon.
    'depends': [
        'base',  # ResUsers, ResCompany, AppendOnlyModel
    ],
    # Eje propio: sin licencia heredada que declarar (DEC-KX-03).
    'license': 'propio',
    'application': False,
    'installable': True,
    'auto_install': True,  # las señales de dominio emiten sin instalación
}
