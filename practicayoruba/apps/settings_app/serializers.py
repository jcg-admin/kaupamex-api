"""
Serializers — SiteSettings (UC-CFG-03)
"""
from rest_framework import serializers
from .models import SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SiteSettings
        fields = [
            'site_name', 'iva_rate', 'currency',
            'order_timeout_minutes', 'max_return_days',
            'free_shipping_threshold', 'updated_at',
        ]
        read_only_fields = ['updated_at']

    def validate_iva_rate(self, value):
        from decimal import Decimal
        if value < Decimal('0.00') or value > Decimal('1.00'):
            raise serializers.ValidationError('Debe estar entre 0.00 y 1.00.')
        return value

    def validate_currency(self, value):
        if len(value) != 3:
            raise serializers.ValidationError('Debe tener exactamente 3 caracteres.')
        return value.upper()

    def validate_order_timeout_minutes(self, value):
        if value < 1:
            raise serializers.ValidationError('Debe ser al menos 1 minuto.')
        return value

    def validate_free_shipping_threshold(self, value):
        from decimal import Decimal
        if value < Decimal('0.00'):
            raise serializers.ValidationError('No puede ser negativo.')
        return value
