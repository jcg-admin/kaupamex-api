"""Serializers — apps.inventory (Sprint 10)."""
from rest_framework import serializers
from apps.settings_app.models import SiteSettings
from .models import ImportJob, StockMovement, StockAlert
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
        fields = ['id', 'product_sku', 'variant_label', 'delta',
                  'stock_before', 'stock_after',
                  'movement_type', 'reason', 'reference', 'notes', 'created_at']

    def get_variant_label(self, obj) -> str | None:
        return obj.variant.option.label if obj.variant else None


class StockAlertSerializer(serializers.ModelSerializer):
    product_sku   = serializers.CharField(source='product.sku', read_only=True)
    variant_label = serializers.SerializerMethodField()

    class Meta:
        model  = StockAlert
        fields = ['id', 'product_sku', 'variant_label',
                  'stock_at_alert', 'resolved', 'created_at']

    def get_variant_label(self, obj) -> str | None:
        return obj.variant.option.label if obj.variant else None


class StockAdjustSerializer(serializers.Serializer):
    """
    UC-INV-04: ajuste manual de stock por delta.
    delta positivo = entrada de mercancía.
    delta negativo = salida / corrección a la baja.
    FR-INV-04.02: el resultado (stock_actual + delta) no puede ser negativo.
    """
    delta = serializers.IntegerField()
    notes = serializers.CharField(required=False, default='', allow_blank=True)


# ─── UC-INV-04 contrato UI: ajuste por nueva cantidad absoluta ───────────────────
ADJUSTMENT_REASONS = [
    'CONTEO_FISICO', 'MERMA', 'ROBO',
    'DEVOLUCION', 'DESCONTINUADO', 'OTRO',
]


class ImportJobSerializer(serializers.ModelSerializer):
    """UC-INV-05: estado y progreso del job de importación CSV."""
    class Meta:
        model  = ImportJob
        fields = ['id', 'status', 'total_rows', 'imported_rows', 'failed_rows', 'created_at']


class VariantAdjustNewQuantitySerializer(serializers.Serializer):
    """
    UC-INV-04 — payload de la UI (UC-INV-01..05 ui agent).
    """
    new_quantity = serializers.IntegerField(required=True)
    reason       = serializers.ChoiceField(choices=ADJUSTMENT_REASONS, required=True)
    observations = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=500,
    )
