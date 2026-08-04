"""``search_history`` — el historial de búsquedas del comprador.

**Forma propia declarada.** La referencia no la tiene: su pariente más
cercano es ``website.track`` (``odoo19c: website/models/website_visitor.py``),
que registra **páginas visitadas** por un ``website.visitor``, no consultas de
búsqueda. Son modelos distintos y el propio ``search_entry.py`` ya lo deja
dicho.

Vive en ``website`` porque aquí vive su modelo (``SearchEntry``). Quien
**escribe** las entradas es el buscador del escaparate
(``website_sale.controllers.main.catalogue_search``); quien las **lee y
borra** es el dueño de la cuenta, y ése es este archivo.

El recurso es CRUD parcial (colección + detalle, sin escritura directa), así
que va como ``ViewSet`` con router — el estilo que el skill ``backend-drf``
fija para colección + detalle. No se expone ``create``: una entrada de
historial la produce el acto de buscar, no un POST del cliente; permitirlo
dejaría inventar historial ajeno a cualquier búsqueda real.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.pagination import PageNumberPagination

from addons.authz.permissions import CapabilityRequiredMixin
from addons.website.controllers.serializers import SearchEntrySerializer
from addons.website.models import SearchEntry


class SearchHistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class SearchHistoryViewSet(CapabilityRequiredMixin,
                           mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet):
    """Historial propio: listar, ver y borrar.

    Gateado por ``account.overview`` —la capacidad de "resumen de cuenta" que
    ``base`` ya declara y siembra—: el historial es una superficie de la
    cuenta propia, no un dominio nuevo. No se inventa una capacidad para
    esto (ver H-API-283).

    El acotamiento por fila es la primera capa: ``get_queryset`` filtra por
    ``request.user``, así que un id ajeno da 404, no 403 — no se confirma la
    existencia de historial de otro.
    """

    required_capability = 'account.overview'
    #: Sólo para que drf-spectacular derive el tipo de ``{id}``; el
    #: acotamiento real lo hace ``get_queryset`` por usuario.
    queryset = SearchEntry.objects.none()
    serializer_class = SearchEntrySerializer
    pagination_class = SearchHistoryPagination
    http_method_names = ['get', 'delete', 'head', 'options']

    def get_queryset(self):
        return SearchEntry.objects.filter(
            user=self.request.user).order_by('-created_at')

    @extend_schema(
        tags=['website'],
        summary='Mi historial de búsquedas',
        responses={200: SearchEntrySerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['website'],
        summary='Una entrada del historial',
        responses={200: SearchEntrySerializer,
                   404: OpenApiResponse(description='No es tuya o no existe')},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['website'],
        summary='Borrar una entrada del historial',
        responses={204: OpenApiResponse(description='Borrada')},
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
