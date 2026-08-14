# Adaptado de Odoo Community `auth_timeout/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03). Allí el addon se
# llama por su disparador ("pedir identidad tras inactividad"); aquí por su
# mecanismo (re-autenticar para elevar la sesión, DEC-12).
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
