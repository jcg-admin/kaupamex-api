"""
Views — apps.catalogue
Sprint 4 — UC-CAT-01: Ver Catálogo
"""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.filters import OrderingFilter
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Product
from .serializers import ProductListSerializer


class CataloguePagination(PageNumberPagination):
    page_size              = 20
    page_size_query_param  = 'page_size'
    max_page_size          = 100


class CatalogueListView(ListAPIView):
    """GET /api/v1/catalogue/ — UC-CAT-01."""
    permission_classes = [AllowAny]
    serializer_class   = ProductListSerializer
    pagination_class   = CataloguePagination
    filter_backends    = [OrderingFilter]
    ordering_fields    = ['price', 'name', 'created_at']
    ordering           = ['-created_at']

    def get_queryset(self):
        qs = Product.objects.filter(
            is_active=True, is_published=True
        ).select_related('category')

        category_slug = self.request.query_params.get('category')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        return qs

    @extend_schema(
        summary='Ver catálogo de productos',
        description='Listado paginado de productos activos y publicados. '
                    'Accesible sin autenticación (FR-CAT-01.01).',
        parameters=[
            OpenApiParameter('category', str, description='Slug de categoría'),
            OpenApiParameter('ordering', str, description='price / -price / name / -created_at'),
        ],
        responses={200: ProductListSerializer(many=True)},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
