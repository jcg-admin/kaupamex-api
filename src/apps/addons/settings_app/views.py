"""
Views — apps.addons.settings_app

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
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.platform.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django.core.cache import cache
from apps.addons.users.audit import audit_log_business
from .models import SiteSettings, PaymentGateway, ShippingMethod, StaticPage, StaticPageVersion, Banner
from .serializers import (
    SiteSettingsSerializer, SiteSettingsAdminSerializer, PublicSiteSettingsSerializer,
    PaymentGatewaySerializer, ShippingMethodSerializer, PublicShippingMethodSerializer,
    ShippingZoneSerializer, PublicShippingZoneSerializer,
    BannerSerializer, PublicBannerSerializer,
)
from .gateway_connector import connector
from rest_framework import serializers as drf_serializers
from apps.addons.orders.proxy_models import ActiveOrder
from apps.addons.orders.models import ShippingZone

logger = logging.getLogger(__name__)




class SiteSettingsView(APIView):
    """
    /api/v1/config/settings/ — excludes deprecated fields (DEC-DOC-005).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

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


class PublicSiteSettingsView(APIView):
    """
    GET /api/v1/config/public-settings/ — public read-only storefront subset.

    US-1.1 (closes ERR-14): the storefront needs a handful of settings
    (tax rate, free-shipping threshold, payment timeout, low-stock threshold)
    without an admin session. This endpoint is unauthenticated and exposes
    ONLY the allowlist defined in PublicSiteSettingsSerializer — never any
    admin, contact, referral or secret field. Read-only (no write methods).
    """
    permission_classes = [AllowAny]
    serializer_class    = PublicSiteSettingsSerializer
    # The singleton settings change rarely; allow short-lived public caching.
    CACHE_MAX_AGE = 300

    @extend_schema(
        summary='Obtener configuración pública del sitio',
        responses={200: PublicSiteSettingsSerializer},
        tags=['config'],
    )
    def get(self, request):
        settings = SiteSettings.get_current()
        response = Response(PublicSiteSettingsSerializer(settings).data)
        response['Cache-Control'] = f'public, max-age={self.CACHE_MAX_AGE}'
        return response


class AdminSiteSettingsView(APIView):
    """
    /api/v1/admin/settings/ — includes all fields including legacy ones (UC-ADM-04).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    @extend_schema(
        summary='Obtener configuración global (admin)',
        responses={200: SiteSettingsAdminSerializer},
        tags=['config'],
    )
    def get(self, request):
        settings = SiteSettings.get_current()
        return Response(SiteSettingsAdminSerializer(settings).data)

    @extend_schema(
        summary='Actualizar configuración global (admin)',
        request=SiteSettingsAdminSerializer,
        responses={200: SiteSettingsAdminSerializer},
        tags=['config'],
    )
    def patch(self, request):
        settings = SiteSettings.get_current()
        serializer = SiteSettingsAdminSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # H-API-NN: sin este BusinessEvent, un cambio de configuracion
        # global es invisible en el audit log de UC-ADM-03 (AuditLogView
        # combina AuthEvent + BusinessEvent + UserDeactivationEvent).
        # BusinessEvent.action no tiene una constante ADMIN_SETTINGS_UPDATED:
        # se escribe el string directo (max_length=30, choices sin
        # constraint DB), mismo patron que ADMIN_REACTIVATE y
        # ADMIN_PERMISSIONS_CHANGED en apps.addons.users.admin_views.
        audit_log_business(
            request.user,
            'ADMIN_SETTINGS_UPDATED',
            request,
            target_type='site_settings',
            target_id=settings.pk,
            extra={'changes': list(serializer.validated_data.keys())},
        )
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
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'settings.view',
        'retrieve': 'settings.view',
        'create': 'settings.create',
        'update': 'settings.edit',
        'partial_update': 'settings.edit',
        'verify': 'settings.edit',
    }
    serializer_class   = PaymentGatewaySerializer
    queryset           = PaymentGateway.objects.all().order_by('gateway')
    http_method_names  = ['get', 'post', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        # H-CICLO104-04: adquirir lock sobre el PaymentGateway dentro de
        # atomic() antes de guardar credenciales. Sin select_for_update() dos
        # admins concurrentes podrian guardar credenciales distintas y la
        # verificacion post-save marcar erroneamente el gateway como verificado
        # con las credenciales del primer request, no del segundo.
        creds_raw = self.request.data.get('credentials_raw')
        with transaction.atomic():
            PaymentGateway.objects.select_for_update().get(pk=serializer.instance.pk)
            instance = serializer.save()
        if creds_raw:
            self._verify_and_mark(instance, creds_raw)

    def _verify_and_mark(self, instance: PaymentGateway, creds: dict):
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
                instance.save(update_fields=['verified_at', 'updated_at'])
        except Exception:
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
            instance.save(update_fields=['verified_at', 'updated_at'])
            return Response({'detail': 'Gateway verificado correctamente.',
                             'verified_at': instance.verified_at})
        return Response({
            'detail': 'El gateway rechazó las credenciales.',
            'codigo_error': 'INVALID_CREDENTIALS',
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
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'settings.view',
        'retrieve': 'settings.view',
        'create': 'settings.create',
        'update': 'settings.edit',
        'partial_update': 'settings.edit',
        'destroy': 'settings.full',
    }
    serializer_class   = ShippingMethodSerializer
    queryset           = ShippingMethod.objects.all().order_by('cost', 'name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
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
        instance.save(update_fields=['is_active', 'updated_at'])

    @extend_schema(summary='Listar métodos de envío', tags=['config'],
                   responses={200: ShippingMethodSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear método de envío', tags=['config'],
                   responses={201: ShippingMethodSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar método de envío', tags=['config'],
                   responses={200: ShippingMethodSerializer})
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


class ShippingZoneViewSet(ModelViewSet):
    """
    Admin CRUD del catálogo de zonas de envío + tiempos de entrega (H-12).

    GET    /api/v2/admin/shipping-zones/       — listar zonas (activas e inactivas)
    POST   /api/v2/admin/shipping-zones/       — crear zona
    PATCH  /api/v2/admin/shipping-zones/<pk>/  — editar zona
    DELETE /api/v2/admin/shipping-zones/<pk>/  — desactivar (soft delete)

    Simétrico a ShippingMethodViewSet. Delete es soft (is_active=False) para
    no romper referencias históricas de cobertura por CP.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'settings.view',
        'retrieve': 'settings.view',
        'create': 'settings.create',
        'update': 'settings.edit',
        'partial_update': 'settings.edit',
        'destroy': 'settings.full',
    }
    serializer_class   = ShippingZoneSerializer
    queryset           = ShippingZone.objects.all().order_by('zip_code_prefix', 'name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])

    @extend_schema(summary='Listar zonas de envío', tags=['config'],
                   responses={200: ShippingZoneSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear zona de envío', tags=['config'],
                   responses={201: ShippingZoneSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar zona de envío', tags=['config'],
                   responses={200: ShippingZoneSerializer})
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(summary='Desactivar zona de envío', responses={204: None}, tags=['config'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class ShippingZoneListPublicView(ListAPIView):
    """GET /api/v2/shipping-zones/ — lista pública de zonas activas (H-12).

    Sin autenticación. El storefront puede consultar la ventana de entrega
    (min/max días) por prefijo de CP para mostrar ETA en checkout.
    """
    permission_classes = [AllowAny]
    serializer_class   = PublicShippingZoneSerializer
    queryset           = ShippingZone.objects.filter(is_active=True).order_by('zip_code_prefix', 'name')

    @extend_schema(summary='Listar zonas de envío activas', tags=['shipping'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ShippingMethodListPublicView(ListAPIView):
    """GET /api/v2/shipping-methods/ — public list of active shipping methods (GAP-C1).

    Unauthenticated. Returns only active methods ordered by cost so the
    checkout can populate shipping options dynamically instead of using
    hardcoded SHIPPING_OPTIONS on the UI side.
    """
    permission_classes = [AllowAny]
    serializer_class   = PublicShippingMethodSerializer
    queryset           = ShippingMethod.objects.filter(is_active=True).order_by('cost', 'name')

    @extend_schema(summary='Listar métodos de envío activos', tags=['shipping'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BannerViewSet(ModelViewSet):
    """Admin CRUD del catálogo de banners de portada (UC-CFG-06, G-CFG-01).

    GET    /api/v2/admin/banners/            — listar (todos, activos e inactivos)
    POST   /api/v2/admin/banners/            — crear
    GET    /api/v2/admin/banners/<pk>/       — ver
    PATCH  /api/v2/admin/banners/<pk>/       — editar
    DELETE /api/v2/admin/banners/<pk>/       — eliminar (hard delete)
    POST   /api/v2/admin/banners/reorder/    — reordenar por placement

    Un único modelo ``Banner`` con ``placement`` (HERO / PROMO_STRIP). El
    storefront lee los activos por placement en el endpoint público.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    permission_map = {
        'list': 'banners.view',
        'retrieve': 'banners.view',
        'create': 'banners.create',
        'update': 'banners.edit',
        'partial_update': 'banners.edit',
        'destroy': 'banners.full',
        'reorder': 'banners.edit',
    }
    serializer_class   = BannerSerializer
    queryset           = Banner.objects.all()
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = Banner.objects.all()
        placement = self.request.query_params.get('placement')
        if placement:
            qs = qs.filter(placement=placement)
        return qs

    @extend_schema(summary='Listar banners', tags=['config'],
                   responses={200: BannerSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary='Crear banner', tags=['config'],
                   responses={201: BannerSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary='Editar banner', tags=['config'],
                   responses={200: BannerSerializer})
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @extend_schema(summary='Eliminar banner', responses={204: None}, tags=['config'])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary='Reordenar banners por placement',
        request={'application/json': {'type': 'object', 'properties': {
            'order': {'type': 'array', 'items': {'type': 'integer'}}}}},
        responses={200: BannerSerializer(many=True)},
        tags=['config'],
    )
    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """POST {'order': [id1, id2, ...]} → asigna ``order`` = índice.

        Todos los ids deben existir y pertenecer al mismo ``placement`` (no se
        mezclan HERO y PROMO_STRIP en una sola reordenación).
        """
        ids = request.data.get('order')
        if not isinstance(ids, list) or not ids:
            raise ValidationError({
                'detail': 'Se requiere "order": lista no vacía de ids.',
                'codigo_error': 'INVALID_REORDER_PAYLOAD',
            })
        banners = list(Banner.objects.filter(pk__in=ids))
        found_ids = {b.pk for b in banners}
        missing = [i for i in ids if i not in found_ids]
        if missing:
            raise ValidationError({
                'detail': f'Banners inexistentes: {missing}.',
                'codigo_error': 'BANNER_NOT_FOUND',
            })
        placements = {b.placement for b in banners}
        if len(placements) > 1:
            raise ValidationError({
                'detail': 'No se pueden reordenar banners de distinto placement.',
                'codigo_error': 'MIXED_PLACEMENT_REORDER',
            })
        by_id = {b.pk: b for b in banners}
        with transaction.atomic():
            for index, banner_id in enumerate(ids):
                banner = by_id[banner_id]
                banner.order = index
                banner.save(update_fields=['order', 'updated_at'])
        result = Banner.objects.filter(pk__in=ids).order_by('order', 'id')
        serializer = self.get_serializer(result, many=True)
        return Response(serializer.data)


class PublicBannerListView(ListAPIView):
    """GET /api/v2/config/banners/?placement=HERO — banners activos (storefront).

    Sin autenticación. Filtra por ``placement`` (query param opcional) y sólo
    devuelve ``is_active=True``, ordenados por ``order``. Proyección pública sin
    campos admin.
    """
    permission_classes = [AllowAny]
    serializer_class   = PublicBannerSerializer

    def get_queryset(self):
        qs = Banner.objects.filter(is_active=True)
        placement = self.request.query_params.get('placement')
        if placement:
            qs = qs.filter(placement=placement)
        return qs.order_by('placement', 'order', 'id')

    @extend_schema(summary='Listar banners activos', tags=['config'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# =============================================================================
# Sprint 10 — UC-CFG-04: Contenido estático con versionado
# =============================================================================



class StaticPageVersionSerializer(drf_serializers.ModelSerializer):
    created_by_username = drf_serializers.CharField(
        source='created_by.email', read_only=True, default=None
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
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.view'
    serializer_class = StaticPageSerializer

    @extend_schema(summary='Listar páginas estáticas', tags=['config'],
                   operation_id='admin_pages_list',
                   responses={200: StaticPageSerializer(many=True)})
    def get(self, request):
        pages = StaticPage.objects.all()
        return Response(StaticPageSerializer(pages, many=True).data)


class StaticPageAdminDetailView(APIView):
    """
    GET /api/v1/admin/pages/<slug>/ — detalle con versión activa.
    UC-CFG-04 (FR-CFG-04.02).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.view'
    serializer_class = StaticPageSerializer

    @extend_schema(summary='Detalle de página estática', tags=['config'],
                   operation_id='admin_pages_retrieve',
                   responses={200: StaticPageSerializer})
    def get(self, request, slug):
        try:
            page = StaticPage.objects.prefetch_related('versions').get(slug=slug)
        except StaticPage.DoesNotExist:
            return Response({'detail': 'Página no encontrada.'}, status=404)
        return Response(StaticPageSerializer(page).data)


# Alias retrocompatible
StaticPageAdminView = StaticPageAdminListView


class PublicStaticPageSerializer(drf_serializers.ModelSerializer):
    """Proyección pública read-only: sólo el contenido de la versión PUBLISHED."""
    content      = drf_serializers.SerializerMethodField()
    slug_display = drf_serializers.CharField(source='get_slug_display', read_only=True)

    class Meta:
        model  = StaticPage
        fields = ['slug', 'slug_display', 'title', 'content', 'updated_at']
        read_only_fields = fields

    def get_content(self, obj):
        version = obj.current_version  # property: última versión PUBLISHED
        return version.content if version else ''


class PublicStaticPageView(APIView):
    """
    GET /api/v2/config/pages/<slug>/ — contenido público de una página estática.
    UC-CFG-04 (H-UI-CFG04-01): expone la versión PUBLISHED para que el
    storefront (/info/:slug) consuma lo que el admin edita, en lugar de un
    módulo hardcodeado. 404 si la página no existe o no tiene versión
    publicada — el frontend cae a su contenido por defecto.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicStaticPageSerializer

    @extend_schema(summary='Contenido público de página estática', tags=['config'],
                   operation_id='public_pages_retrieve',
                   responses={200: PublicStaticPageSerializer})
    def get(self, request, slug):
        try:
            page = StaticPage.objects.prefetch_related('versions').get(slug=slug)
        except StaticPage.DoesNotExist:
            return Response({'detail': 'Página no encontrada.'}, status=404)
        if page.current_version is None:
            return Response({'detail': 'Página sin versión publicada.'}, status=404)
        return Response(PublicStaticPageSerializer(page).data)


class StaticPagePublishView(APIView):
    """POST /api/v1/admin/pages/<slug>/publish/ — publicar nueva versión."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'
    serializer_class = StaticPagePublishSerializer

    @extend_schema(summary='Publicar nueva versión de página estática', tags=['config'],
                   responses={201: StaticPageVersionSerializer})
    def post(self, request, slug):
        page, _ = StaticPage.objects.get_or_create(
            slug=slug,
            defaults={'title': dict(StaticPage.PAGE_CHOICES).get(slug, slug)},
        )
        s = StaticPagePublishSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        publish_at = s.validated_data.get('publish_at')
        is_immediate = not publish_at

        # H-CICLO92-01: envolver en transaction.atomic() + select_for_update()
        # sobre la pagina para serializar peticiones concurrentes al mismo slug.
        # Sin esto dos requests concurrentes computan el mismo next_version y
        # uno falla con IntegrityError no capturado (unique_together(page,version)).
        with transaction.atomic():
            # Re-fetch with lock so no concurrent publish wins the same version.
            page = StaticPage.objects.select_for_update().get(pk=page.pk)

            if is_immediate:
                StaticPageVersion.objects.filter(
                    page=page, status=StaticPageVersion.STATUS_PUBLISHED
                ).update(status=StaticPageVersion.STATUS_ARCHIVED, updated_at=timezone.now())

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
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'
    serializer_class = StaticPageVersionSerializer

    @extend_schema(summary='Revertir a versión anterior', tags=['config'],
                   responses={201: StaticPageVersionSerializer})
    def post(self, request, slug, version):
        try:
            old = StaticPageVersion.objects.select_related('page').get(
                page__slug=slug, version=version
            )
        except StaticPageVersion.DoesNotExist:
            return Response({'detail': 'Versión no encontrada.'}, status=404)

        # H-CICLO92-01: mismo patron que StaticPagePublishView — proteger el
        # calculo de next_version con select_for_update + transaction.atomic().
        with transaction.atomic():
            page = StaticPage.objects.select_for_update().get(pk=old.page_id)

            StaticPageVersion.objects.filter(
                page=page, status=StaticPageVersion.STATUS_PUBLISHED
            ).update(status=StaticPageVersion.STATUS_ARCHIVED, updated_at=timezone.now())

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


class StaticPageStatusV2View(APIView):
    """PATCH /api/v2/admin/pages/<slug>/status/ — Tier B.

    v1 used POST /pages/<slug>/publish/; v2 uses PATCH /pages/<slug>/status/.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    def patch(self, request, slug):
        return StaticPagePublishView().post(request, slug=slug)


class StaticPageRestorationV2View(APIView):
    """POST /api/v2/admin/pages/<slug>/restorations/ — Tier B.

    v1 had version number in URL path (/versions/<v>/restore/).
    v2 takes version from request body: {"version": N}.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'settings.edit'

    def post(self, request, slug):
        version_raw = request.data.get('version')
        if version_raw is None:
            return Response(
                {'detail': 'version requerido.', 'codigo_error': 'VERSION_REQUIRED'},
                status=400,
            )
        try:
            version = int(version_raw)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'version debe ser un entero.', 'codigo_error': 'INVALID_VERSION'},
                status=400,
            )
        return StaticPageRestoreView().post(request, slug=slug, version=version)
