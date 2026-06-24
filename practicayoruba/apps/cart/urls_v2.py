"""URLs — apps.cart v2 (F2: cart, wishlist, account/referral, notifications)."""
from django.urls import path

from .views import (
    CartView,
    CartItemListView,
    CartItemDetailView,
    CartSaveView,
    CartMergeView,
    CartVoucherView,
)

app_name = 'cart_v2'

urlpatterns = [
    path('',                 CartView.as_view(),           name='cart'),
    path('items/',           CartItemListView.as_view(),   name='cart-items'),
    path('items/<int:pk>/',  CartItemDetailView.as_view(), name='cart-item-detail'),
    path('snapshots/',       CartSaveView.as_view(),       name='cart-snapshots'),
    path('merges/',          CartMergeView.as_view(),      name='cart-merges'),
    path('voucher/',         CartVoucherView.as_view(),    name='cart-voucher'),
]
