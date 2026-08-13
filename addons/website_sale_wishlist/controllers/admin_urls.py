"""URLs admin — ``website_sale_wishlist`` (agregado de marketing).

Montado en ``config/urls.py`` bajo el prefijo compartido ``api/v2/admin/``:
  path('api/v2/admin/', include(('addons.website_sale_wishlist.controllers.admin_urls',
       'admin_wishlist'), namespace='admin_wishlist_v2'))
"""
from django.urls import path

from addons.website_sale_wishlist.controllers.main import WishlistAggregateView

app_name = 'admin_wishlist_v2'

urlpatterns = [
    path('wishlist/aggregate/', WishlistAggregateView.as_view(),
         name='wishlist-aggregate'),
]
