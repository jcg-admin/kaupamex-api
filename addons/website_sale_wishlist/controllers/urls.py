"""URLs — ``website_sale_wishlist`` (superficie del comprador).

Montado en ``config/urls.py``:
  path('api/v2/wishlist/', include(('addons.website_sale_wishlist.controllers.urls',
       'wishlist'), namespace='wishlist_v2'))
"""
from django.urls import path

from addons.website_sale_wishlist.controllers.main import (
    WishlistItemDetailView,
    WishlistMoveToCartView,
    WishlistView,
)

app_name = 'wishlist_v2'

urlpatterns = [
    path('', WishlistView.as_view(), name='wishlist'),
    path('<int:pk>/', WishlistItemDetailView.as_view(), name='wishlist-item'),
    path('<int:pk>/cart-transfers/', WishlistMoveToCartView.as_view(),
         name='wishlist-cart-transfers'),
]
