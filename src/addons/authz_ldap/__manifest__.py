# Adaptado de Odoo Community `auth_ldap/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Autenticación via LDAP',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': 'Federación de identidad contra un directorio LDAP',
    # La referencia declara ['base', 'base_setup']. `base_setup` es el addon
    # que hospeda `res.config.settings` (la UI de ajustes); este árbol no lo
    # tiene y su rol aquí lo cumplen la propia API DRF del recurso + los
    # SystemParameter de `base` — por eso no aparece. `company` entra porque
    # la configuración es por-Company (FK medida en models.py); en la
    # referencia ese modelo vive en `base`, aquí en su addon propio.
    # `authz` entra por la capacidad que gatea el CRUD (permissions.ldap).
    'depends': [
        'authz',
        'base',
        'company',
    ],
    # Igual que la referencia: python-ldap compila contra libldap/libsasl del
    # sistema, así que es dependencia EXTERNA opcional (extra `ldap` de
    # pyproject.toml; `uv sync --extra ldap`). Sin ella el addon carga y
    # degrada: LDAP_AVAILABLE=False y autenticar federado falla explícito.
    'external_dependencies': {
        'python': ['python-ldap'],
        'apt': {
            'python-ldap': 'python3-ldap',
        },
    },
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
