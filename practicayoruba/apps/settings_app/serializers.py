"""
Serializers — apps.settings_app

Sprint 1:  SiteSettingsSerializer
Sprint 8:  PaymentGatewaySerializer, ShippingMethodSerializer
"""
from decimal import Decimal
from rest_framework import serializers
from .models import SiteSettings, PaymentGateway, ShippingMethod


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
