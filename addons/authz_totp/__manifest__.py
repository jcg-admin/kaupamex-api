# Adaptado de Odoo Community `auth_totp/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03). El renombre
# `auth_*` → `authz_*` es de este árbol; ver tarea #20.
{
    'name': 'Segundo factor TOTP',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'TotpSecret y TotpRecoveryCode: alta del segundo factor, verificación '
        'del código de seis dígitos y códigos de recuperación de un solo uso'
    ),
    # `depends` MEDIDO contra los imports reales.
    #
    # `web` entró al cablear el segundo paso del login: `controllers/main.py`
    # importa de `addons.web.controllers.session` las dos claves de la sesión
    # parcial y el productor del cuerpo de sesión. La referencia declara
    # ['web'] igual, aunque por otro motivo —el bundle de assets del asistente
    # de alta, que este monolito no sirve: esa pantalla es de `ui`—. La
    # dirección coincide; el consumo no.
    'depends': [
        'base',   # ResUsers, SystemParameter (services.py:17, data.py:13)
        'authz',  # la capacidad que gatea el CRUD (controllers/main.py:18)
        'web',    # PRE_UID_KEY, build_session_info (controllers/main.py:65)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
