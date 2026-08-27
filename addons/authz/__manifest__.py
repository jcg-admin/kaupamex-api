# Forma propia: no adapta un addon concreto de la referencia. Su análogo allí
# es el control de acceso que vive DENTRO de `base` (`ir.model.access`,
# `res.groups`), no un addon aparte — ver H-API-562.
{
    'name': 'Autorización por capacidad',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'Capability, Role, RoleAssignment, DirectEntitlement y el catálogo de '
        'módulos: el motor fail-closed que gatea toda vista DRF (DEC-11)'
    ),
    # `depends` MEDIDO da cinco destinos; sólo se declara UNO. Los otros cuatro
    # son aristas que invierten la dirección de la referencia y declararlas
    # aquí las legitimaría en vez de registrarlas — mismo criterio con que
    # `sale` omite `sale_loyalty`. El gate de dirección
    # (`scripts/check_addon_cycles.py`) es su dueño; el desenlace, la tarea
    # #322:
    #
    #   authz_audit        services.py, controllers/main.py, controllers/admin_main.py
    #   authz_reauth       services.py:35, controllers/main.py:19
    #   sale_subscription  management/commands/reconcile_catalog.py:42
    #   website            controllers/main.py:18, management/commands/seed_menu.py:19
    #
    # `observability` salió de la lista el 2026-08-20: sus dos consumos desde
    # `admin_main.py` eran eventos de **autorización** emitidos contra
    # `BusinessEvent` con cadenas fuera de su vocabulario; hoy van a
    # `AuthzEvent`, que ya era arista declarada (:ref:`h-api-753`).
    #
    # Las dos últimas son las más claras: un addon fundacional importando
    # negocio. En la referencia los satélites (`auth_*`) dependen del núcleo,
    # nunca al revés.
    'depends': [
        'base',  # ResUsers, ResCompany, ir.model, SystemParameter, los mixins
    ],
    # Eje propio: sin licencia heredada que declarar (DEC-KX-03).
    'license': 'propio',
    'application': False,
    'installable': True,
    'auto_install': True,  # ninguna vista DRF resuelve sin el motor de capacidad
}
