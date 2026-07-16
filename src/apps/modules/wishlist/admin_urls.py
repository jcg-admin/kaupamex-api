"""
URLs admin — apps.modules.wishlist.

Mounted in config/urls.py:
  path('api/v2/admin/', include(('apps.modules.wishlist.admin_urls', 'admin_wishlist'),
       namespace='admin_wishlist_v2'))
"""
from django.urls import path
from .views import WishlistAggregateView

app_name = 'admin_wishlist_v2'

urlpatterns = [
    path('wishlist/aggregate/',
         WishlistAggregateView.as_view(),
         name='admin-wishlist-aggregate'),
]
