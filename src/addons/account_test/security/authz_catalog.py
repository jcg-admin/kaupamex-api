"""Declaración de capacidad de ``account_test`` (DEC-11).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()`` —
ver ``security/__init__.py`` para el mapeo desde
``security/ir.model.access.csv`` de la referencia.

No declara ``MODULES``: reutiliza el módulo comercial ``finance``, ya
declarado por ``account`` (``src/addons/account/authz_catalog.py``) —
``CapabilitySpec.module`` se deriva por defecto del prefijo antes del punto
(``'finance.diagnostics'.split('.', 1)[0]`` == ``'finance'``), así que no
hace falta repetir el ``ModuleSpec``. Esto es exactamente el caso que el
contrato documenta: *"capacidades... cuelgan de un módulo real"* sin exigir
que el addon que las declara sea el mismo que declaró el módulo.
"""
from addons.authz.declaration import CapabilitySpec

CAPABILITIES = [
    CapabilitySpec(
        code='finance.diagnostics',
        name='Ejecutar pruebas de consistencia contable',
        is_sensitive=True,
    ),
]
