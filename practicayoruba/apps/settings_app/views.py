"""
Views — apps.settings_app

Sprint 1: SiteSettingsView
Sprint 8: PaymentGatewayViewSet (UC-CFG-01), ShippingMethodViewSet (UC-CFG-02)
"""
import csv
import io
import logging
import uuid
from decimal import Decimal, InvalidOperation
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django.core.cache import cache
from .models import SiteSettings, PaymentGateway, ShippingMethod, StaticPage, StaticPageVersion
from .serializers import SiteSettingsSerializer, PaymentGatewaySerializer, ShippingMethodSerializer
from .gateway_connector import connector
from rest_framework import serializers as drf_serializers
from apps.orders.proxy_models import ActiveOrder

logger = logging.getLogger(__name__)




class SiteSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Obtener configuración global',
        responses={200: SiteSettingsSerializer},
        tags=['config'],
    )
    def get(self, request):
        settings = SiteSettings.get_current()
        return Response(SiteSettingsSerializer(settings).data)

    @extend_schema(
        summary='Actualizar configuración global',
        request=SiteSettingsSerializer,
        responses={200: SiteSettingsSerializer},
        tags=['config'],
    )
    def patch(self, request):
        settings = SiteSettings.get_current()
        serializer = SiteSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# =============================================================================
# Sprint 8 — UC-CFG-01: Gateways de pago
# =============================================================================

class PaymentGatewayViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/gateways/       — listar gateways
    POST   /api/v1/admin/gateways/       — crear gateway
    GET    /api/v1/admin/gateways/<pk>/  — ver gateway (credenciales enmascaradas)
    PATCH  /api/v1/admin/gateways/<pk>/  — actualizar credenciales / activar-desactivar
    POST   /api/v1/admin/gateways/<pk>/verify/ — verificar conectividad

    UC-CFG-01 (FR-CFG-01.02).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = PaymentGatewaySerializer
    queryset           = PaymentGateway.objects.all().order_by('gateway')
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        """Si se envían credenciales nuevas, verificar conectividad."""
        creds_raw = self.request.data.get('credentials_raw')
        instance = serializer.save()
        if creds_raw:
            self._verify_and_mark(instance, creds_raw)

    def _verify_and_mark(self, instance: PaymentGateway, creds: dict):
        """Verifica conectividad y actualiza verified_at si OK."""
        try:
            if instance.gateway == PaymentGateway.GATEWAY_MERCADOPAGO:
                ok = connector.verify_mercadopago(creds.get('access_token', ''))
            elif instance.gateway == PaymentGateway.GATEWAY_PAYPAL:
                ok = connector.verify_paypal(
                    creds.get('client_id', ''), creds.get('client_secret', '')
                )
            else:
                ok = False

            if ok:
                instance.verified_at = timezone.now()
                instance.save(update_fields=['verified_at'])
        except Exception:
            # silent OK because EX-02 del FR: el guardado no se bloquea
            # ante fallo de red, pero el incidente queda loggeado para
            # operaciones. DEC-DOC-008.
            logger.warning(
                'post-save gateway verify failed gw=%s (EX-02 FR)',
                getattr(instance, 'gateway', '?'), exc_info=True,
            )

    @action(detail=True, methods=['post'], url_path='verify')
    @extend_schema(
        summary='Verificar conectividad del gateway',
        responses={
            200: OpenApiResponse(description='Gateway verificado correctamente.'),
            400: OpenApiResponse(description='Credenciales inválidas o gateway no responde.'),
        },
        tags=['config'],
    )
    def verify(self, request, pk=None):
        """POST /api/v1/admin/gateways/<pk>/verify/ — verifica con credenciales actuales."""
        instance = self.get_object()
        creds = instance.get_credentials()
        if not creds:
            return Response({'detail': 'No hay credenciales configuradas.'}, status=400)
        try:
            if instance.gateway == PaymentGateway.GATEWAY_MERCADOPAGO:
                ok = connector.verify_mercadopago(creds.get('access_token', ''))
            elif instance.gateway == PaymentGateway.GATEWAY_PAYPAL:
                ok = connector.verify_paypal(
                    creds.get('client_id', ''), creds.get('client_secret', '')
                )
            else:
                ok = False
        except Exception as e:
            return Response({'detail': f'Error de red: {e}'}, status=503)

        if ok:
            instance.verified_at = timezone.now()
            instance.save(update_fields=['verified_at'])
            return Response({'detail': 'Gateway verificado correctamente.',
                             'verified_at': instance.verified_at})
        return Response({
            'detail': 'El gateway rechazó las credenciales.',
            'codigo_error': 'CREDENCIALES_INVALIDAS',
        }, status=400)


# =============================================================================
# Sprint 8 — UC-CFG-02: Metodos de envio
# =============================================================================

class ShippingMethodViewSet(ModelViewSet):
    """
    GET    /api/v1/admin/shipping-methods/       — listar metodos activos e inactivos
    POST   /api/v1/admin/shipping-methods/       — crear metodo
    GET    /api/v1/admin/shipping-methods/<pk>/  — ver metodo
    PATCH  /api/v1/admin/shipping-methods/<pk>/  — editar metodo
    DELETE /api/v1/admin/shipping-methods/<pk>/  — desactivar (soft delete)

    UC-CFG-02 (FR-CFG-02.02).
    Proteccion de ordenes activas: resuelto via ActiveOrder proxy (H-ORD-005).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = ShippingMethodSerializer
    queryset           = ShippingMethod.objects.all().order_by('cost', 'name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        """
        Soft delete: is_active=False.
        Sprint 14: verificar ordenes en estado PENDING/PROCESSING.
        """
        active_orders = ActiveOrder.objects.filter(
            shipping_method=instance,
        ).count()
        if active_orders > 0:
            raise ValidationError({
                'detail': (
                    f'Este método tiene {active_orders} orden(es) activa(s). '
                    'Espera a que se procesen antes de desactivarlo.'
                ),
                'codigo_error': 'METHOD_WITH_ACTIVE_ORDERS',
            })
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @extend_schema(summary='Listar métodos de envío', tags=['config'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear método de envío', tags=['config'])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar método de envío', tags=['config'])
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary='Desactivar método de envío',
        responses={204: None},
        tags=['config'],
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


# =============================================================================
# Sprint 10 — UC-CFG-04: Contenido estático con versionado
# =============================================================================



class StaticPageVersionSerializer(drf_serializers.ModelSerializer):
    created_by_username = drf_serializers.CharField(
        source='created_by.username', read_only=True, default=None
    )
    class Meta:
        model  = StaticPageVersion
        fields = ['id', 'version', 'content', 'status',
                  'created_by_username', 'created_at', 'publish_at']
        read_only_fields = ['id', 'version', 'created_at']


class StaticPageSerializer(drf_serializers.ModelSerializer):
    current_version = StaticPageVersionSerializer(read_only=True)
    slug_display    = drf_serializers.CharField(source='get_slug_display', read_only=True)

    class Meta:
        model  = StaticPage
        fields = ['id', 'slug', 'slug_display', 'title', 'current_version', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class StaticPagePublishSerializer(drf_serializers.Serializer):
    content    = drf_serializers.CharField()
    publish_at = drf_serializers.DateTimeField(required=False, allow_null=True)


class StaticPageAdminListView(APIView):
    """
    GET /api/v1/admin/pages/ — listar páginas estáticas.
    UC-CFG-04 (FR-CFG-04.02).

    Split de StaticPageAdminView (D-032 T-6): el detail se separo en
    StaticPageAdminDetailView para evitar colision de operationId.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StaticPageSerializer

    @extend_schema(summary='Listar páginas estáticas', tags=['config'],
                   operation_id='admin_pages_list')
    def get(self, request):
        pages = StaticPage.objects.all()
        return Response(StaticPageSerializer(pages, many=True).data)


class StaticPageAdminDetailView(APIView):
    """
    GET /api/v1/admin/pages/<slug>/ — detalle con versión activa.
    UC-CFG-04 (FR-CFG-04.02).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StaticPageSerializer

    @extend_schema(summary='Detalle de página estática', tags=['config'],
                   operation_id='admin_pages_retrieve')
    def get(self, request, slug):
        try:
            page = StaticPage.objects.prefetch_related('versions').get(slug=slug)
        except StaticPage.DoesNotExist:
            return Response({'detail': 'Página no encontrada.'}, status=404)
        return Response(StaticPageSerializer(page).data)


# Alias retrocompatible
StaticPageAdminView = StaticPageAdminListView


class StaticPagePublishView(APIView):
    """POST /api/v1/admin/pages/<slug>/publish/ — publicar nueva versión."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StaticPagePublishSerializer

    @extend_schema(summary='Publicar nueva versión de página estática', tags=['config'])
    def post(self, request, slug):
        page, _ = StaticPage.objects.get_or_create(
            slug=slug,
            defaults={'title': dict(StaticPage.PAGE_CHOICES).get(slug, slug)},
        )
        s = StaticPagePublishSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        publish_at = s.validated_data.get('publish_at')
        is_immediate = not publish_at

        # Archivar versión activa si existe
        if is_immediate:
            StaticPageVersion.objects.filter(
                page=page, status=StaticPageVersion.STATUS_PUBLISHED
            ).update(status=StaticPageVersion.STATUS_ARCHIVED)

        # Calcular siguiente número de versión
        last = page.versions.order_by('-version').first()
        next_version = (last.version + 1) if last else 1

        new_status = (StaticPageVersion.STATUS_PUBLISHED
                      if is_immediate else StaticPageVersion.STATUS_DRAFT)

        version = StaticPageVersion.objects.create(
            page=page,
            version=next_version,
            content=s.validated_data['content'],
            status=new_status,
            created_by=request.user,
            publish_at=publish_at,
        )
        return Response(StaticPageVersionSerializer(version).data, status=201)


class StaticPageRestoreView(APIView):
    """POST /api/v1/admin/pages/<slug>/versions/<version>/restore/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = StaticPageVersionSerializer

    @extend_schema(summary='Revertir a versión anterior', tags=['config'])
    def post(self, request, slug, version):
        try:
            old = StaticPageVersion.objects.get(
                page__slug=slug, version=version
            )
        except StaticPageVersion.DoesNotExist:
            return Response({'detail': 'Versión no encontrada.'}, status=404)

        page = old.page
        # Archivar la actual
        StaticPageVersion.objects.filter(
            page=page, status=StaticPageVersion.STATUS_PUBLISHED
        ).update(status=StaticPageVersion.STATUS_ARCHIVED)

        last = page.versions.order_by('-version').first()
        next_version = last.version + 1

        restored = StaticPageVersion.objects.create(
            page=page,
            version=next_version,
            content=old.content,
            status=StaticPageVersion.STATUS_PUBLISHED,
            created_by=request.user,
        )
        return Response(StaticPageVersionSerializer(restored).data, status=201)
