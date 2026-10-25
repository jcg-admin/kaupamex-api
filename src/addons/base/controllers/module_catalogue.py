"""Consulta del catálogo técnico; no ejecuta solicitudes de instalación."""
from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.pagination import PageNumberPagination

from addons.authz.permissions import CapabilityRequiredMixin
from addons.base.models.ir_module import IrModule


class TechnicalModuleSerializer(serializers.ModelSerializer):
    """Separa versión disponible de versión instalada conocida."""

    category = serializers.CharField(source='category_path', read_only=True)

    class Meta:
        model = IrModule
        fields = (
            'id', 'name', 'shortdesc', 'summary', 'category', 'application',
            'auto_install', 'license', 'version', 'installed_version',
            'state', 'icon',
        )
        read_only_fields = fields


class TechnicalModuleFilters(serializers.Serializer):
    """Filtros admitidos; el cliente no puede elegir conexión ni orden SQL."""

    search = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(required=False, allow_blank=True)
    state = serializers.ChoiceField(choices=IrModule.STATES, required=False)
    application = serializers.BooleanField(required=False)

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields) - {'page', 'page_size', 'format'}
        if unknown:
            raise serializers.ValidationError({
                key: 'Parámetro no admitido.' for key in sorted(unknown)
            })
        return super().to_internal_value(data)


class TechnicalModulePagination(PageNumberPagination):
    """Paginación estable y acotada del catálogo técnico."""

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class TechnicalModuleViewSet(CapabilityRequiredMixin, viewsets.ReadOnlyModelViewSet):
    """Lee el catálogo en el contexto de base resuelto por el runtime vigente."""

    required_capability = 'settings.modules'
    serializer_class = TechnicalModuleSerializer
    pagination_class = TechnicalModulePagination

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return IrModule.objects.none()
        # Un dict evita que BooleanField interprete la ausencia HTML como False.
        filters = TechnicalModuleFilters(data=self.request.query_params.dict())
        if not filters.is_valid():
            raise serializers.ValidationError({
                'codigo_error': 'VALIDATION_ERROR',
                'errors': filters.errors,
            })
        values = dict(filters.validated_data)
        search = values.pop('search', '')
        if 'category' in values:
            values['category_path'] = values.pop('category')
        queryset = IrModule.objects.filter(**values)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(shortdesc__icontains=search)
                | Q(summary__icontains=search)
            )
        return queryset.order_by('-application', 'sequence', 'name', 'pk')

    @extend_schema(
        tags=['technical-modules'], summary='Consultar módulos técnicos',
        parameters=[TechnicalModuleFilters],
        responses={
            200: TechnicalModuleSerializer(many=True),
            400: OpenApiResponse(description='VALIDATION_ERROR: filtros inválidos'),
            401: OpenApiResponse(description='NOT_AUTHENTICATED: sesión requerida'),
            403: OpenApiResponse(description='PERMISSION_DENIED: capacidad requerida'),
        },
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['technical-modules'], summary='Consultar un módulo técnico',
        responses={
            200: TechnicalModuleSerializer,
            400: OpenApiResponse(description='VALIDATION_ERROR: filtros inválidos'),
            401: OpenApiResponse(description='NOT_AUTHENTICATED: sesión requerida'),
            403: OpenApiResponse(description='PERMISSION_DENIED: capacidad requerida'),
            404: OpenApiResponse(description='NOT_FOUND: módulo no encontrado'),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
