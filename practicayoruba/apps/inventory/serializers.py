"""Serializers — apps.inventory (Sprint 10)."""
from rest_framework import serializers
from apps.settings_app.models import SiteSettings
from .models import StockMovement, StockAlert
from .services import _get_stock_status


class StockDashboardSerializer(serializers.Serializer):
    """UC-INV-01: item del dashboard de inventario."""
    product_id    = serializers.IntegerField()
    product_name  = serializers.CharField()
    sku           = serializers.CharField()
    variant_id    = serializers.IntegerField(allow_null=True)
    variant_label = serializers.CharField(allow_null=True)
    stock         = serializers.IntegerField()
    status        = serializers.CharField()
    threshold     = serializers.IntegerField()


class StockMovementSerializer(serializers.ModelSerializer):
    product_sku   = serializers.CharField(source='product.sku', read_only=True)
    variant_label = serializers.SerializerMethodField()

    class Meta:
        model  = StockMovement
        fields = ['id', 'product_sku', 'variant_label', 'delta', 'stock_after',
                  'movement_type', 'reference', 'notes', 'created_at']

    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None


class StockAlertSerializer(serializers.ModelSerializer):
    product_sku   = serializers.CharField(source='product.sku', read_only=True)
    variant_label = serializers.SerializerMethodField()

    class Meta:
        model  = StockAlert
        fields = ['id', 'product_sku', 'variant_label',
                  'stock_at_alert', 'resolved', 'created_at']

    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None


class StockAdjustSerializer(serializers.Serializer):
    """UC-INV-04: ajuste manual de stock."""
    new_stock  = serializers.IntegerField(min_value=0)
    notes      = serializers.CharField(required=False, default='', allow_blank=True)
