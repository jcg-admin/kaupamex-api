"""URLs del historial de búsquedas — ``website``.

Montado en ``config/urls.py``::

    path('api/v2/search/', include(('addons.website.controllers.search_urls',
         'search'), namespace='search_v2'))

Módulo aparte de ``urls.py`` (páginas públicas, bajo ``api/v2/config/``)
porque cuelga de otro prefijo: el historial es del comprador, no de la
configuración del sitio. Mismo criterio que ``delivery``, que separa
``urls.py`` de ``webhook_urls.py`` por destino.

Va por **router**: es un recurso con colección y detalle, y un
``.as_view({...})`` manual sobre un ViewSet se salta las
``permission_classes`` por acción.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from addons.website.controllers.search_history import SearchHistoryViewSet

app_name = 'search'

router = DefaultRouter()
router.register(r'history', SearchHistoryViewSet, basename='search-history')

urlpatterns = [
    path('', include(router.urls)),
]
