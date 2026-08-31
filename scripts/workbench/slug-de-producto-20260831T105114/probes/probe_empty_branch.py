"""La rama del slug vacio, y si display_name difiere de name en un producto.

La fuente (`odoo19c: addons/http_routing/models/ir_http.py::_slug`) hace
`if not slugname: return str(identifier)` — sin el guion suelto. Y lee
`value.display_name`, no `value.name`.
"""
import django

django.setup()

from addons.base.models.ir_http import IrHttp  # noqa: E402
from addons.product.models import ProductTemplate  # noqa: E402

for name in ['!!!', '---', '   ', '### $$$', 'ok']:
    print(f'slugify_one({name!r}) = {IrHttp.slugify_one(name)!r}')

campo = ProductTemplate._meta.get_field('name')
print('name:', campo.name)
print('display_name declarado en ProductTemplate:',
      hasattr(ProductTemplate, 'display_name'))
