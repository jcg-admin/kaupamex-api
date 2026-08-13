"""URLs — carrito del escaparate (``website_sale``).

Montado en ``config/urls.py``::

    path('api/v2/cart/', include(('addons.website_sale.controllers.urls',
         'cart'), namespace='cart_v2'))

Los nombres de ruta siguen el contrato REST del SPA, no los paths QWeb de la
referencia (``/shop/cart/add`` → ``POST cart/items/``): la correspondencia
ruta-a-ruta está tabulada en el docstring de ``cart.py``.

Las líneas van por **router** y no por ``path()`` porque son un recurso CRUD:
un ``.as_view({...})`` manual sobre un ViewSet se salta las
``permission_classes`` declaradas por acción, que es un hueco de seguridad,
no una preferencia de estilo.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from addons.website_sale.controllers.cart import (
    CartItemViewSet,
    CartView,
    CartVoucherView,
    merge_cart,
    save_cart_for_later,
)

app_name = 'cart_v2'

router = DefaultRouter()
router.register(r'items', CartItemViewSet, basename='cart-item')

urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('voucher/', CartVoucherView.as_view(), name='cart-voucher'),
    path('merges/', merge_cart, name='cart-merges'),
    path('snapshots/', save_cart_for_later, name='cart-snapshots'),
    path('', include(router.urls)),
]
