"""
Serializers — addons.settings_app

Sprint 1:  SiteSettingsSerializer
Sprint 8:  PaymentGatewaySerializer, ShippingMethodSerializer
"""
from decimal import Decimal
from rest_framework import serializers
from addons.delivery.models import ShippingZone
from addons.delivery.estimation import delivery_estimate_dict
from addons.base_address_extended.models import CatalogPostalCode
from addons.payment.models import PaymentGateway
from addons.base.models import SiteSettings
from addons.delivery.models import ShippingMethod
from addons.website.models import Banner


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SiteSettings
        # Excluding deprecated fields: currency, site_name, order_timeout_minutes, max_return_days
        # (removed per migration 0008_sync_model_drift / DEC-DOC-005)
        fields = [
            'id', 'iva_rate',
            'payment_timeout_minutes', 'min_stock_threshold',
            'free_shipping_threshold',
            'support_email', 'phone', 'address', 'social_links',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate_social_links(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'social_links debe ser un objeto JSON (dict).'
            )
        allowed_keys = {'facebook', 'instagram', 'twitter', 'youtube', 'tiktok', 'whatsapp'}
        for key, url in value.items():
            if key not in allowed_keys:
                raise serializers.ValidationError(
                    f'Clave no permitida: "{key}". '
                    f'Claves validas: {sorted(allowed_keys)}.'
                )
            if not isinstance(url, str):
                raise serializers.ValidationError(
                    f'El valor de "{key}" debe ser una cadena de texto.'
                )
        return value


class PublicSiteSettingsSerializer(serializers.ModelSerializer):
    """
    US-1.1 (closes ERR-14): storefront-safe subset of SiteSettings exposed
    through the public (unauthenticated) endpoint.

    Explicit field allowlist — deliberately does NOT reuse the admin/config
    serializer so that no contact, identity, referral or secret field can
    leak through GET /api/v1/config/public-settings/. Any new field added to
    SiteSettings must be opted-in here explicitly to become public.
    """

    class Meta:
        model  = SiteSettings
        fields = [
            'iva_rate',
            'free_shipping_threshold',
            'payment_timeout_minutes',
            'min_stock_threshold',
        ]
        read_only_fields = fields


class SiteSettingsAdminSerializer(serializers.ModelSerializer):
    """
    H-CICLO40-07: AdminSiteSettingsView importaba SiteSettingsAdminSerializer
    que no existia en serializers.py, rompiendo la importacion del modulo y
    levantando ImportError en cada peticion al endpoint /admin/settings/.
    El serializer admin incluye todos los campos del modelo (incluidos los
    campos legacy que el serializer publico excluye) para que el admin pueda
    gestionar la configuracion completa del sistema (UC-ADM-04).
    """

    class Meta:
        model  = SiteSettings
        fields = [
            'id',
            'site_name', 'currency',
            'iva_rate',
            'payment_timeout_minutes', 'order_timeout_minutes',
            'max_return_days', 'min_stock_threshold',
            'free_shipping_threshold',
            'support_email', 'phone', 'address', 'social_links',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate_social_links(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'social_links debe ser un objeto JSON (dict).'
            )
        allowed_keys = {'facebook', 'instagram', 'twitter', 'youtube', 'tiktok', 'whatsapp'}
        for key, url in value.items():
            if key not in allowed_keys:
                raise serializers.ValidationError(
                    f'Clave no permitida: "{key}". '
                    f'Claves validas: {sorted(allowed_keys)}.'
                )
            if not isinstance(url, str):
                raise serializers.ValidationError(
                    f'El valor de "{key}" debe ser una cadena de texto.'
                )
        return value


# =============================================================================
# Sprint 8 — UC-CFG-01: Gateways de pago
# =============================================================================

class PaymentGatewaySerializer(serializers.ModelSerializer):
    """
    UC-CFG-01 — Lectura: credenciales enmascaradas (nunca en claro).
    Escritura: credentials_raw → se cifran con Fernet antes de guardar.
    Actualizado tras migración 0007: provider→gateway, credentials_enc→credentials.
    """
    credentials     = serializers.SerializerMethodField(read_only=True)
    credentials_raw = serializers.JSONField(
        write_only=True, required=False, default=dict,
        help_text='Credenciales en claro. Se cifran al guardar. No se retornan en la respuesta.',
    )
    gateway_display = serializers.CharField(
        source='get_gateway_display', read_only=True,
    )

    class Meta:
        model  = PaymentGateway
        fields = [
            'id', 'name', 'gateway', 'gateway_display',
            'is_active', 'credentials', 'credentials_raw',
            'verified_at', 'updated_at',
        ]
        read_only_fields = ['id', 'verified_at', 'updated_at']

    def get_credentials(self, obj) -> dict:
        """Retorna credenciales enmascaradas (nunca en claro)."""
        return obj.get_masked_credentials()

    def validate_credentials_raw(self, value: dict) -> dict:
        """Validación de formato por gateway."""
        gateway = self.initial_data.get('gateway') or (
            self.instance.gateway if self.instance else None
        )
        if gateway == PaymentGateway.GATEWAY_MERCADOPAGO:
            if 'access_token' not in value:
                raise serializers.ValidationError(
                    {'access_token': 'Requerido para MercadoPago.'}
                )
        elif gateway == PaymentGateway.GATEWAY_PAYPAL:
            for field in ('client_id', 'client_secret'):
                if field not in value:
                    raise serializers.ValidationError(
                        {field: f'Requerido para PayPal.'}
                    )
        return value

    def create(self, validated_data):
        creds_raw = validated_data.pop('credentials_raw', {})
        instance = super().create(validated_data)
        if creds_raw:
            instance.set_credentials(creds_raw)
            instance.save(update_fields=['credentials', 'updated_at'])
        return instance

    def update(self, instance, validated_data):
        creds_raw = validated_data.pop('credentials_raw', None)
        instance = super().update(instance, validated_data)
        if creds_raw is not None:
            instance.set_credentials(creds_raw)
            instance.verified_at = None
            instance.save(update_fields=['credentials', 'verified_at', 'updated_at'])
        return instance


# =============================================================================
# Sprint 8 — UC-CFG-02: Metodos de envio
# =============================================================================

class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ShippingMethod
        fields = [
            'id', 'name', 'cost', 'estimated_days',
            'is_active', 'free_threshold', 'zones', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate_cost(self, value):
        if value < Decimal('0.00'):
            raise serializers.ValidationError('El costo no puede ser negativo.')
        return value

    def validate_estimated_days(self, value):
        if value < 1:
            raise serializers.ValidationError('El tiempo estimado debe ser al menos 1 dia habil.')
        return value


class PublicShippingMethodSerializer(serializers.ModelSerializer):
    """Read-only projection for the buyer-facing /api/v2/shipping-methods/ endpoint.

    Omits admin-only fields: is_active, zones, updated_at.
    """
    class Meta:
        model  = ShippingMethod
        fields = ['id', 'name', 'cost', 'estimated_days', 'free_threshold']
        read_only_fields = fields


class ShippingZoneSerializer(serializers.ModelSerializer):
    """Admin CRUD del catálogo de zonas + tiempos de entrega (H-12).

    Relación con SEPOMEX (``addons.geo.CatalogPostalCode``): el ``zip_code_prefix``
    de una zona se ancla al catálogo oficial de códigos postales — se valida que
    el prefijo cubra ≥1 CP real y se expone ``coverage`` (estados + nº de
    asentamientos que abarca) para que el admin vea qué cubre antes de guardar.
    """
    coverage = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = ShippingZone
        fields = [
            'id', 'name', 'zip_code_prefix', 'is_active',
            'estimated_days_min', 'estimated_days_max', 'cost',
            'free_threshold', 'coverage',
        ]
        read_only_fields = ['id', 'coverage']

    def get_coverage(self, obj):
        """Cobertura SEPOMEX del prefijo: estados + nº de asentamientos."""
        qs = CatalogPostalCode.objects.filter(
            country='MX', postal_code__startswith=obj.zip_code_prefix)
        states = list(
            qs.values_list('state', flat=True).distinct().order_by('state')[:20])
        return {'settlement_count': qs.count(), 'states': states}

    def validate_zip_code_prefix(self, value):
        """Ancla el prefijo a SEPOMEX: debe cubrir ≥1 CP mexicano real.

        Graceful: si el catálogo SEPOMEX aún no está cargado (dev/test sin el
        loader T-206), se omite la validación para no bloquear — la relación
        aplica cuando hay datos oficiales contra los cuales validar.
        """
        catalog = CatalogPostalCode.objects.filter(country='MX')
        if catalog.exists() and not catalog.filter(
                postal_code__startswith=value).exists():
            raise serializers.ValidationError(
                f'El prefijo «{value}» no corresponde a ningún código postal '
                f'mexicano en el catálogo SEPOMEX.'
            )
        return value

    def validate(self, attrs):
        # El máximo no puede ser menor que el mínimo cuando ambos están dados.
        lo = attrs.get('estimated_days_min',
                       getattr(self.instance, 'estimated_days_min', None))
        hi = attrs.get('estimated_days_max',
                       getattr(self.instance, 'estimated_days_max', None))
        if lo is not None and hi is not None and hi < lo:
            raise serializers.ValidationError({
                'estimated_days_max':
                    'El máximo de días no puede ser menor que el mínimo.',
            })
        return attrs


class PublicShippingZoneSerializer(serializers.ModelSerializer):
    """Proyección pública read-only del catálogo de zonas (/api/v2/shipping-zones/).

    Incluye ``delivery_estimate`` (G-ENV-02): la ventana de fechas "Recíbelo"
    calculada con la regla de corte 11:00 + días hábiles sin domingo. Depende de
    ``now`` (no cacheable) — es una estimación viva para el storefront."""
    delivery_estimate = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = ShippingZone
        fields = [
            'id', 'name', 'zip_code_prefix',
            'estimated_days_min', 'estimated_days_max', 'cost',
            'free_threshold', 'delivery_estimate',
        ]
        read_only_fields = fields

    def get_delivery_estimate(self, obj):
        return delivery_estimate_dict(obj)


class _BannerImageUrlMixin:
    """image_url absoluto si hay request en contexto; '' si no hay imagen."""

    def get_image_url(self, obj):
        if not obj.image:
            return ''
        url = obj.image.url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class BannerSerializer(_BannerImageUrlMixin, serializers.ModelSerializer):
    """Serializer admin del catálogo de banners (UC-CFG-06, G-CFG-01).

    Expone ``image_url`` (lectura) además del ``image`` de subida (escritura)
    para el formulario del panel admin."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = Banner
        fields = ['id', 'image', 'image_url', 'placement', 'title', 'alt_text',
                  'link_url', 'is_active', 'order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'image_url', 'created_at', 'updated_at']
        extra_kwargs = {'image': {'write_only': True}}


class PublicBannerSerializer(_BannerImageUrlMixin, serializers.ModelSerializer):
    """Proyección pública read-only del banner (storefront)."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = Banner
        fields = ['id', 'image_url', 'placement', 'title', 'alt_text',
                  'link_url', 'order']
        read_only_fields = fields
