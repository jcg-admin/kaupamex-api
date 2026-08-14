# Adaptado de Odoo Community `auth_passkey/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Passkeys',
    'version': '1.1',
    'category': 'Hidden/Tools',
    'summary': 'Inicio de sesión con Passkey (WebAuthn)',
    # La referencia declara ['base_setup', 'web'] con auto_install: aparece
    # en toda instalación con web. Aquí ninguno de los dos existe (ver los
    # mapas de authz_ldap/authz_oauth); las dependencias reales medidas son
    # `base` (usuario) y `authz` (capacidad + reauth del ciclo de gestión).
    # auto_install se conserva fiel.
    'depends': [
        'authz',
        'base',
    ],
    'auto_install': True,
    # La referencia VENDORIZA la librería webauthn (_vendor/, 4537 loc);
    # aquí es dependencia declarada en pyproject.toml (webauthn>=2.8.0) —
    # ver H-API-228.
    'external_dependencies': {
        'python': ['webauthn'],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
