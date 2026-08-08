"""URLs del escaparate — ``website_sale`` (vitrina, no carrito).

Montado en ``config/urls.py`` bajo la raíz de v2, porque sus rutas cuelgan de
prefijos distintos (``products/``, ``categories/``, ``catalogue/``)::

    path('api/v2/', include(('addons.website_sale.controllers.shop_urls',
         'shop'), namespace='shop_v2'))

Es el mismo patrón que ``delivery`` ya usa para ``logistics``. El addon tiene
más de un módulo de URLs —``urls.py`` (carrito) y éste— igual que ``delivery``
tiene ``urls.py`` y ``webhook_urls.py``.

**Orden de resolución con las reseñas.** ``rating`` monta
``products/<int:product_id>/reviews/`` antes que este módulo. No hay colisión:
aquella tiene tres segmentos y ``products/<slug:slug>/`` sólo uno, así que
Django nunca las confunde. El listado (``products/``) tampoco choca.
"""
from django.urls import path

from addons.website_sale.controllers.main import (
    CategoryTreeView,
    ProductListView,
    catalogue_search,
    product_detail,
    product_related,
)

app_name = 'shop'

urlpatterns = [
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<slug:slug>/', product_detail, name='product-detail'),
    path('products/<slug:slug>/related/', product_related,
         name='product-related'),
    path('categories/', CategoryTreeView.as_view(), name='category-tree'),
    path('catalogue/search/', catalogue_search, name='catalogue-search'),
]
