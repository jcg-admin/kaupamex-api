"""
Views — apps.settings_app

Sprint 1: SiteSettingsView
Sprint 8: PaymentGatewayViewSet (UC-CFG-01), ShippingMethodViewSet (UC-CFG-02)
"""
import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
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

from .models import SiteSettings, PaymentGateway, ShippingMethod
from .serializers import (
    SiteSettingsSerializer,
    PaymentGatewaySerializer,
    ShippingMethodSerializer,
)
from .gateway_connector import connector


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
    queryset           = PaymentGateway.objects.all().order_by('provider')
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
            if instance.provider == PaymentGateway.PROVIDER_MP:
                ok = connector.verify_mercadopago(creds.get('access_token', ''))
            elif instance.provider == PaymentGateway.PROVIDER_PAYPAL:
                ok = connector.verify_paypal(
                    creds.get('client_id', ''), creds.get('client_secret', '')
                )
            else:
                ok = False

            if ok:
                instance.verified_at = timezone.now()
                instance.save(update_fields=['verified_at'])
        except Exception:
            # Fallo de red — no bloquear el guardado (EX-02 del FR)
            pass

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
            if instance.provider == PaymentGateway.PROVIDER_MP:
                ok = connector.verify_mercadopago(creds.get('access_token', ''))
            elif instance.provider == PaymentGateway.PROVIDER_PAYPAL:
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
    Proteccion de ordenes: TODO Sprint 12.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class   = ShippingMethodSerializer
    queryset           = ShippingMethod.objects.all().order_by('cost', 'name')
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        """
        Soft delete: is_active=False.
        TODO Sprint 12: verificar ordenes activas antes de desactivar.
        """
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
