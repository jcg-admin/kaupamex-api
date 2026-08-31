"""display_name frente a name en ProductTemplate.

`odoo19c: addons/http_routing/models/ir_http.py::_slug` compone el slug con
`value.display_name`, no con `value.name`. Si aqui los dos difieren, portar
la fuente cambia el contrato que el SPA ya consume — y eso es decision, no
derivacion.
"""
import django

django.setup()

from addons.product.models import ProductTemplate  # noqa: E402

for name in ['Camisa Azul', 'Café Orgánico', '手工皂']:
    obj = ProductTemplate(name=name, default_code='SKU-1')
    print(f'name={obj.name!r:<20} display_name={obj.display_name!r}'
          f'  iguales={obj.name == obj.display_name}')
