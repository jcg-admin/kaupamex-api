"""URLs — carrito del escaparate (``website_sale``).

Montado en ``config/urls.py``::

    path('api/v2/cart/', include(('addons.website_sale.controllers.urls',
         'cart'), namespace='cart_v2'))

Los nombres de ruta siguen el contrato REST del SPA, no los paths QWeb de la
referencia (``/shop/cart/add`` → ``POST cart/items/``): la correspondencia
ruta-a-ruta está tabulada en el docstring de ``main.py``.
"""
from django.urls import path

from addons.website_sale.controllers.main import (
    CartItemDetailView,
    CartItemsView,
    CartMergesView,
    CartSnapshotsView,
    CartVoucherView,
    CartView,
)

app_name = 'cart_v2'

urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('items/', CartItemsView.as_view(), name='cart-items'),
    path('items/<int:pk>/', CartItemDetailView.as_view(),
         name='cart-item-detail'),
    path('voucher/', CartVoucherView.as_view(), name='cart-voucher'),
    path('merges/', CartMergesView.as_view(), name='cart-merges'),
    path('snapshots/', CartSnapshotsView.as_view(), name='cart-snapshots'),
]
