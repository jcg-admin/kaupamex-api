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
    # `depends` MEDIDO contra los imports reales. La referencia declara ['web']
    # —el bundle de assets del asistente de alta—, que este monolito no sirve:
    # la pantalla es de `ui` y aquí sólo vive el endpoint DRF.
    'depends': [
        'base',   # ResUsers, SystemParameter (services.py:17, data.py:13)
        'authz',  # la capacidad que gatea el CRUD (controllers/main.py:18)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
