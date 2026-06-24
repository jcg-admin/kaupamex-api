"""URLs — apps.wishlist v2 (F2)."""
from django.urls import path

from .views import WishlistView, WishlistItemDetailView, WishlistMoveToCartView

app_name = 'wishlist_v2'

urlpatterns = [
    path('',                          WishlistView.as_view(),            name='wishlist'),
    path('<int:pk>/',                  WishlistItemDetailView.as_view(),  name='wishlist-item'),
    path('<int:pk>/cart-transfers/',   WishlistMoveToCartView.as_view(),  name='wishlist-cart-transfers'),
]
