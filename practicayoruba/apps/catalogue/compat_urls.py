"""
Compat URLs — apps.catalogue.

El storefront (UI ``catalogSlice.js``) consume ``/api/v2/catalogue/*`` para
listar productos, ver el detalle y listar categorías, mientras que la API
canónica expone esas vistas bajo ``/api/v2/products/`` y ``/api/v2/categories/``
(consolidación F8). Estas rutas mapean el prefijo ``/api/v2/catalogue/`` a las
MISMAS vistas para que la tienda funcione contra el backend real sin reescribir
el front ni su batería de mocks/tests.

Montado en ``config/urls.py`` DESPUÉS de ``browse_public_urls`` (que sirve
``/api/v2/catalogue/search/``) para que ``search/`` no sea capturado como
``<slug>``.

Deuda conocida: el camino limpio a futuro es migrar ``catalogSlice.js`` a
``/api/v2/products/`` + ``/api/v2/categories/`` (como ya hicieron los hooks de
búsqueda) y retirar este alias.
"""
from django.urls import path

from .views import CategoryListView, ProductDetailView, ProductListV2View

app_name = 'catalogue_compat'

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='compat-category-list'),
    path('', ProductListV2View.as_view(), name='compat-product-list'),
    path('<slug:slug>/', ProductDetailView.as_view(), name='compat-product-detail'),
]
