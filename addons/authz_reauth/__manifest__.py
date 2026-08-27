# Adaptación del decorador `check_identity` de Odoo Community
# (`odoo19c: odoo/addons/base/models/res_users.py:87-127`, LGPL-3) — atribución
# y aviso de licencia preservados (DEC-KX-03).
#
# H-API-767: esta cabecera decía adaptar `auth_timeout/__manifest__.py`, y es
# el addon equivocado. `auth_timeout` (que sólo existe en 19, no en 18c) aporta
# OTRO eje: el candado por tiempo — `lock_timeout` absoluto que fuerza logout y
# `lock_timeout_inactivity` que exige confirmar identidad, ambos configurables
# por grupo (`res_groups.py:37-54`). Ese eje **no está aquí**; su porte es la
# tarea #640. Lo que este addon implementa es el otro mecanismo de la
# referencia: el step-up por acción, que en Odoo es un decorador sobre el
# método y aquí es una consulta al catálogo de capacidades.
{
    'name': 'Re-autenticación para acciones sensibles',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'ReauthSession: ventana de sesión elevada que una acción sensible '
        'exige fresca (assert_session_fresh), y su caducidad'
    ),
    # `depends` MEDIDO da tres destinos; se declaran DOS. La referencia declara
    # ['auth_totp', 'auth_totp_mail', 'auth_passkey', 'bus'] — sus cuatro
    # segundos factores más el canal de notificación. Aquí el segundo factor
    # NO es dependencia: `authz_reauth` expone el mecanismo y son los addons
    # de factor (`authz_totp`, `authz_passkey`) los que lo consumen, que es la
    # dirección que el gate vigila.
    #
    # La arista medida `authz_reauth → authz` (`reauth.py:14-15`) NO se
    # declara: `authz` ya mide `authz_reauth` de vuelta (`services.py:35`), y
    # declarar ambas fija el ciclo en el grafo. Cuál de las dos se invierte lo
    # decide la tarea #322 — ver H-API-562.
    'depends': [
        'base',         # ResUsers, ResCompany, SystemParameter (el TTL)
        'authz_audit',  # AuthzEvent — cada elevación deja rastro (reauth.py:16-17)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
