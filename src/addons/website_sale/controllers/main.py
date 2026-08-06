"""``main`` — el escaparate: listado, ficha y categorías.

Origen y correspondencia
========================

Adaptación de ``odoo19c: addons/website_sale/controllers/main.py`` (LGPL-3)
sobre ``odoo-tools@622ddc2a``. Este archivo hospeda lo que la referencia pone
en ``main.py``: **la vitrina**. El carrito vive en ``cart.py`` y el pago en
``payment.py``, igual que allá.

Las rutas de la vitrina en ``odoo19c`` se construyen sobre la constante
``SHOP_PATH`` (``const.py:438``), no como literales — por eso un ``grep`` de
``@route('/shop'`` **no las encuentra** aunque existan. Están en
``main.py:274-289``:

===================================================  =========================
Referencia (``odoo19c``)                             Aquí
===================================================  =========================
``SHOP_PATH``                        (``:276``)      ``GET /api/v2/products/``
``{SHOP_PATH}/page/<int:page>``      (``:277``)      ``?page=`` del listado
``{SHOP_PATH}/category/<category>``  (``:278``)      ``?category=`` del listado
``def product(…)``                   (``:564``)      ``GET /api/v2/products/<slug>/``
===================================================  =========================

Dos superficies son **forma propia declarada**, y su motivo es el mismo: la
referencia renderiza QWeb, así que su listado ya trae dentro las facetas y
los relacionados; un SPA los pide por separado.

- ``GET /api/v2/categories/`` — el árbol de categorías. Allá es contexto del
  render de ``shop()``; aquí es un recurso propio.
- ``GET /api/v2/products/<slug>/related/`` — allá se calcula dentro de
  ``product()``; aquí se pide aparte para no engordar la ficha.
- ``GET /api/v2/catalogue/search/`` — la búsqueda con ``normalized_query``.
  El listado ya acepta ``?search=`` (como la referencia); esta ruta añade
  **el registro de la consulta** en ``SearchEntry``, que la referencia no
  tiene (su análogo, ``website.track``, registra páginas visitadas, no
  consultas).

El **slug** replica ``ir.http._slug``: ``<nombre-slugificado>-<id>``. La
referencia resuelve el registro por el id final del slug
(``_unslug``), no por el texto — el texto es sólo legibilidad y SEO. Aquí es
idéntico: se parte por el último guion y se busca por id.

Publicación
===========

El listado sólo muestra ``is_published=True``. El campo lo aporta
``website.published.mixin`` (``addons.website.models.mixins``), que es quien
lo dueña en la referencia — ver el docstring de ``ProductTemplate``.
"""
import re

from django.db.models import Q
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    OpenApiTypes,
    extend_schema,
)
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.product.models import ProductCategory, ProductTemplate
from addons.website.models import SearchEntry
from addons.website_sale.controllers.serializers import (
    CategoryTreeSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)

#: ``<texto>-<id>`` — el id final es lo que resuelve el registro.
_SLUG_ID = re.compile(r'-(\d+)$')


def _product_id_from_slug(slug):
    """≙ ``ir.http._unslug``: el id vive al final; el texto es decorativo.

    Devuelve ``None`` si el slug no lleva id — un slug sin id no identifica
    nada, así que la vista responde 404 en vez de adivinar por nombre.
    """
    match = _SLUG_ID.search(slug or '')
    return int(match.group(1)) if match else None


def _published_products():
    """La base del escaparate: publicados y vendibles.

    ``is_published`` es la decisión del sitio; ``sale_ok`` y ``active`` son
    del ERP. Las tres tienen que cumplirse — un producto despublicado no se
    muestra aunque sea vendible, y uno archivado tampoco aunque siga
    publicado.
    """
    return (
        ProductTemplate.objects
        .filter(is_published=True, sale_ok=True, active=True)
        .select_related('categ', 'uom')
    )


class ShopPagination(PageNumberPagination):
    """≙ ``{SHOP_PATH}/page/<int:page>`` (``odoo19c: main.py:277``).

    La referencia pagina por path; aquí por query param, que es la forma
    REST. El envelope es el de siempre (``count``/``next``/``previous``/
    ``results``) porque el SPA ya lo consume.
    """

    page_size = 24
    page_size_query_param = 'page_size'
    max_page_size = 96


class ProductListView(ListAPIView):
    """≙ ``shop()`` (``odoo19c: main.py:290``) — el listado del escaparate.

    Se portan los filtros que la referencia acepta en su firma
    (``page``, ``category``, ``search``, ``min_price``, ``max_price``); no se
    portan ``tags`` ni ``ppg``/``ppr`` (disposición de la rejilla), que son
    del render QWeb.

    Pública: la referencia declara ``auth='public'`` — un escaparate que
    exige cuenta para mirar no es un escaparate.
    """

    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = ShopPagination

    @extend_schema(
        tags=['catalogue'],
        summary='Listar productos publicados',
        parameters=[
            OpenApiParameter('search', OpenApiTypes.STR,
                             description='Busca en nombre y descripción.'),
            OpenApiParameter('category', OpenApiTypes.INT,
                             description='Id de categoría (incluye hijas).'),
            OpenApiParameter('min_price', OpenApiTypes.NUMBER),
            OpenApiParameter('max_price', OpenApiTypes.NUMBER),
            OpenApiParameter('page', OpenApiTypes.INT),
            OpenApiParameter('page_size', OpenApiTypes.INT),
        ],
        responses={200: ProductListSerializer(many=True)},
        auth=[],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        params = self.request.query_params
        queryset = _published_products()

        search = (params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description_sale__icontains=search)
                | Q(default_code__icontains=search)
            )

        category = params.get('category')
        if category and category.isdigit():
            # Incluye la descendencia: pedir "Ropa" y no ver lo que cuelga de
            # "Ropa / Camisas" sorprendería al comprador. ``parent_path`` es
            # el materialized path que ya mantiene ProductCategory.
            node = ProductCategory.objects.filter(pk=int(category)).first()
            if node is not None and node.parent_path:
                queryset = queryset.filter(
                    categ__parent_path__startswith=node.parent_path)
            else:
                queryset = queryset.filter(categ_id=int(category))

        for param, lookup in (('min_price', 'gte'), ('max_price', 'lte')):
            raw = params.get(param)
            if raw:
                try:
                    queryset = queryset.filter(**{f'list_price__{lookup}': raw})
                except (ValueError, TypeError):
                    # silent OK because un precio no numérico es ruido de la
                    # query string, no un error del comprador: se ignora el
                    # filtro en vez de devolver 400 y dejar la vitrina en
                    # blanco. La excepción es acotada (ValueError/TypeError),
                    # no un `except Exception`.
                    pass

        return queryset.order_by('sequence', 'name')


@extend_schema(
    tags=['catalogue'],
    summary='Ficha de un producto',
    responses={
        200: ProductDetailSerializer,
        404: OpenApiResponse(description='PRODUCT_NOT_FOUND'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def product_detail(request, slug):
    """≙ ``product()`` (``odoo19c: main.py:564``).

    Un verbo, un recurso → vista función. El slug se resuelve por su id
    final, igual que ``_unslug``.
    """
    product_id = _product_id_from_slug(slug)
    product = (
        _published_products().filter(pk=product_id).first()
        if product_id else None
    )
    if product is None:
        return Response(
            {'codigo_error': 'PRODUCT_NOT_FOUND',
             'detail': 'El producto no existe o no está publicado.'},
            status=status.HTTP_404_NOT_FOUND)
    return Response(ProductDetailSerializer(product).data)


@extend_schema(
    tags=['catalogue'],
    summary='Productos relacionados',
    responses={
        200: ProductListSerializer(many=True),
        404: OpenApiResponse(description='PRODUCT_NOT_FOUND'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def product_related(request, slug):
    """Relacionados de una ficha — forma propia (ver docstring del módulo).

    Criterio: misma categoría, excluyendo el propio producto. Es el mismo
    que usa la referencia para su bloque "alternativos" cuando el producto no
    declara ``alternative_product_ids`` a mano.
    """
    product_id = _product_id_from_slug(slug)
    product = (
        _published_products().filter(pk=product_id).first()
        if product_id else None
    )
    if product is None:
        return Response(
            {'codigo_error': 'PRODUCT_NOT_FOUND',
             'detail': 'El producto no existe o no está publicado.'},
            status=status.HTTP_404_NOT_FOUND)

    related = (
        _published_products()
        .filter(categ_id=product.categ_id)
        .exclude(pk=product.pk)
        .order_by('sequence', 'name')[:12]
    )
    return Response(ProductListSerializer(related, many=True).data)


@extend_schema(
    tags=['catalogue'],
    summary='Buscar en el catálogo (registra la consulta)',
    parameters=[
        OpenApiParameter('q', OpenApiTypes.STR, required=True,
                         description='Texto a buscar.'),
    ],
    responses={
        200: OpenApiResponse(description='results + normalized_query'),
        400: OpenApiResponse(description='SEARCH_QUERY_REQUIRED'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def catalogue_search(request):
    """Búsqueda del escaparate — el listado con ``?search=`` **más registro**.

    Forma propia declarada: la referencia acepta ``search`` dentro de
    ``shop()`` y no guarda nada; su ``website.track`` registra páginas
    visitadas, no consultas. Aquí la consulta se guarda en ``SearchEntry``
    (``addons.website``) para alimentar el historial del comprador.

    El registro es **best-effort y sólo con sesión**: un anónimo busca igual,
    simplemente no se le guarda nada — no hay a quién colgárselo.
    """
    raw = (request.query_params.get('q') or '').strip()
    if not raw:
        return Response(
            {'codigo_error': 'SEARCH_QUERY_REQUIRED',
             'detail': 'Falta el texto a buscar (parámetro q).'},
            status=status.HTTP_400_BAD_REQUEST)

    normalized = ' '.join(raw.lower().split())
    results = (
        _published_products()
        .filter(Q(name__icontains=raw)
                | Q(description_sale__icontains=raw)
                | Q(default_code__icontains=raw))
        .order_by('sequence', 'name')[:50]
    )
    payload = ProductListSerializer(
        results, many=True, context={'request': request}).data

    if request.user.is_authenticated:
        SearchEntry.objects.create(
            user=request.user, query=raw[:200],
            normalized_query=normalized[:200], results_count=len(payload),
        )

    return Response({
        'normalized_query': normalized,
        'count': len(payload),
        'results': payload,
    })


class CategoryTreeView(ListAPIView):
    """El árbol de categorías — forma propia (ver docstring del módulo).

    Devuelve sólo las raíces con su descendencia anidada: el SPA arma el menú
    de una sola petición en vez de N por nivel.
    """

    permission_classes = [AllowAny]
    serializer_class = CategoryTreeSerializer
    pagination_class = None

    @extend_schema(
        tags=['catalogue'],
        summary='Árbol de categorías de la tienda',
        responses={200: CategoryTreeSerializer(many=True)},
        auth=[],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            ProductCategory.objects
            .filter(parent__isnull=True)
            .prefetch_related('child_id')
            .order_by('name')
        )
