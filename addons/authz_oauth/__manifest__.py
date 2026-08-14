# Adaptado de Odoo Community `auth_oauth/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Autenticación OAuth2',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': 'Login federado contra proveedores OAuth2/OIDC',
    # La referencia declara ['base', 'web', 'base_setup', 'auth_signup'].
    # `web` no existe aquí (la página de login con botones la pinta el SPA,
    # que consume el endpoint público de proveedores); `base_setup` no aplica
    # (la superficie de configuración es el CRUD DRF). `authz_signup` entra
    # igual que en la referencia: el alta federada respeta su política
    # (`signup_open()`), y `authz` por la capacidad del CRUD.
    'depends': [
        'authz',
        'authz_signup',
        'base',
    ],
    # `requests` valida el access_token contra el proveedor (la referencia lo
    # trae vendorizado en su runtime; aquí es dependencia declarada en
    # pyproject.toml).
    'external_dependencies': {
        'python': ['requests'],
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
