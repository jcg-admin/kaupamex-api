"""URLs — apps.cart (Sprint 12)."""
from django.urls import path
from .views import CartView, CartItemView, CartSaveView, CartMergeView, CartVoucherView

app_name = 'cart'

urlpatterns = [
    path('',              CartView.as_view(),       name='cart'),
    path('items/',        CartItemView.as_view(),   name='cart-items'),
    path('items/<int:pk>/', CartItemView.as_view(), name='cart-item-detail'),
    path('save/',         CartSaveView.as_view(),   name='cart-save'),
    path('merge/',        CartMergeView.as_view(),  name='cart-merge'),
    path('voucher/',      CartVoucherView.as_view(), name='cart-voucher'),
]
