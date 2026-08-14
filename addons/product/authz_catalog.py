"""Declaración del catálogo L0 que dueña ``product`` (#179, SOL-100).

Recogido por ``seed_authz`` vía ``addons.authz.declaration.discover()``.

Por qué este código es de este addon:

- ``catalogue`` — el catálogo de producto. El addon homónimo se retiró
  (``api@115d219``), cuyo mensaje ya nombraba el destino: *"catalogue →
  product + website_sale"*. La referencia coincide: el catálogo es
  ``product.template``/``product.product``
  (``odoo19c: addons/product/models/product_template.py``,
  ``odoo-tools@622ddc2a``). ``website_sale`` publica el catálogo, no lo dueña.

El módulo ``catalogue`` es la raíz del grafo de dependencias comerciales:
``inventory`` depende de él, ``orders`` de ambos. Por eso ``depends=()``.
"""
from addons.authz.declaration import CapabilitySpec, ModuleSpec

MODULES = [
    ModuleSpec(
        code='catalogue',
        name='Catálogo',
        is_application=True,
        category='Order Management',
    ),
]

CAPABILITIES = [
    CapabilitySpec(code='catalogue', name='Catálogo'),
]
