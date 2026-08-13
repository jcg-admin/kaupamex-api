# Forma propia: la referencia no tiene un addon de observabilidad — su
# instrumentación vive dispersa en el servidor (`odoo/service/`, el logger
# de `http.py`), no como modelo consultable.
{
    'name': 'Observabilidad',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'RequestLog y BusinessEvent: la petición sellada por middleware y el '
        'evento de negocio, los dos consultables por DRF para el operador L0'
    ),
    # `depends` MEDIDO da ['authz', 'base']; se declara sólo `base`. La arista
    # a `authz` es el gate de capacidad de `AdminLogsView`, no una dependencia
    # de datos — mismo criterio que `base_setup` y `bus`.
    #
    # NOTA de dirección: `authz` mide de vuelta `observability`
    # (`controllers/admin_main.py:40`). Ese par está dentro del ciclo que
    # H-API-562 registra; su desenlace es la tarea #322.
    'depends': [
        'base',  # ResUsers, ResCompany, AppendOnlyModel
    ],
    # Eje propio: sin licencia heredada que declarar (DEC-KX-03).
    'license': 'propio',
    'application': False,
    'installable': True,
    'auto_install': True,  # el middleware sella TODA petición
}
