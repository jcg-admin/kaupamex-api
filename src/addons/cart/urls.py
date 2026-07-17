"""
URLs — addons.cart (F8 consolidation).

Mounted in config/urls.py:
  path('api/v2/cart/', include(('addons.cart.urls', 'cart'), namespace='cart_v2'))
"""
from django.urls import path
from .views import CartView, CartItemListView, CartItemDetailView, CartSaveView, CartMergeView, CartVoucherView

app_name = 'cart'

urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('items/', CartItemListView.as_view(), name='cart-items'),
    path('items/<int:pk>/', CartItemDetailView.as_view(), name='cart-item-detail'),
    path('snapshots/', CartSaveView.as_view(), name='cart-snapshots'),
    path('merges/', CartMergeView.as_view(), name='cart-merges'),
    path('voucher/', CartVoucherView.as_view(), name='cart-voucher'),
]
