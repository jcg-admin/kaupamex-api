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
    # SystemParameter de `base` — por eso no aparece. La configuración es
    # por-ResCompany (FK medida en models.py), y ese modelo vive en `base`,
    # igual que en la referencia: `company` se disolvió (#19/#35) y ya no
    # existe como addon, así que la FK la cubre `base`.
    # `authz` entra por la capacidad que gatea el CRUD (permissions.ldap).
    'depends': [
        'authz',
        'base',
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
