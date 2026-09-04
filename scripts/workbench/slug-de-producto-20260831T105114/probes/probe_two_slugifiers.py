"""Los dos slugify sobre el mismo nombre: el de Django y el portado.

`website_sale/controllers/serializers.py:43` usa el de Django; su hermano
`website_sale_wishlist/.../serializers.py:44` usa `IrHttp.slugify_one`. La
sonda mide si los dos coinciden, y sobre qué entrada divergen.
"""
import django
from django.utils.text import slugify as django_slugify

django.setup()

from addons.base.models.ir_http import IrHttp  # noqa: E402  (tras setup)

NAMES = [
    'Camisa Azul',
    'Café Orgánico',
    'ハンドメイド 石鹸',
    '手工皂',
    'صابون يدوي',
    'Ñandú_edición 2026',
    'Ω omega',
]

print(f'{"nombre":<24} {"django":<28} {"portado":<28} coinciden')
for name in NAMES:
    a = django_slugify(name)
    b = IrHttp.slugify_one(name)
    print(f'{name:<24} {a!r:<28} {b!r:<28} {a == b}')
