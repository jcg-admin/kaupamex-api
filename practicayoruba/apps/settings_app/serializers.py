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
        fields = [
            'id', 'site_name', 'iva_rate', 'currency',
            'order_timeout_minutes', 'max_return_days',
            'free_shipping_threshold', 'min_stock_threshold',
            'avatar_max_size_mb', 'max_addresses_per_user',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


# =============================================================================
# Sprint 8 — UC-CFG-01: Gateways de pago
# =============================================================================

class PaymentGatewaySerializer(serializers.ModelSerializer):
    """
    Lectura: credenciales enmascaradas.
    Escritura: credenciales en claro → se cifran antes de guardar.
    """
    credentials     = serializers.SerializerMethodField(read_only=True)
    credentials_raw = serializers.JSONField(
        write_only=True, required=False, default=dict,
        help_text='Credenciales en claro. Se cifran al guardar. No se retornan en la respuesta.',
    )
    provider_display = serializers.CharField(
        source='get_provider_display', read_only=True
    )

    class Meta:
        model  = PaymentGateway
        fields = [
            'id', 'provider', 'provider_display',
            'is_active', 'credentials', 'credentials_raw',
            'verified_at', 'updated_at',
        ]
        read_only_fields = ['id', 'verified_at', 'updated_at']

    def get_credentials(self, obj) -> dict:
        """Retorna credenciales enmascaradas (nunca en claro)."""
        return obj.get_masked_credentials()

    def validate_credentials_raw(self, value: dict) -> dict:
        """Validacion de formato por provider."""
        provider = self.initial_data.get('provider') or (
            self.instance.provider if self.instance else None
        )
        if provider == PaymentGateway.PROVIDER_MP:
            if 'access_token' not in value:
                raise serializers.ValidationError(
                    {'access_token': 'Requerido para MercadoPago.'}
                )
        elif provider == PaymentGateway.PROVIDER_PAYPAL:
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
            instance.save(update_fields=['credentials_enc'])
        return instance

    def update(self, instance, validated_data):
        creds_raw = validated_data.pop('credentials_raw', None)
        instance = super().update(instance, validated_data)
        if creds_raw is not None:
            instance.set_credentials(creds_raw)
            instance.save(update_fields=['credentials_enc', 'verified_at'])
        return instance


# =============================================================================
# Sprint 8 — UC-CFG-02: Metodos de envio
# =============================================================================

class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ShippingMethod
        fields = [
            'id', 'name', 'description', 'cost', 'estimated_days',
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
