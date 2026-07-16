"""Serializers — apps.modules.inventory (Sprint 10)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.modules.settings_app.models import SiteSettings
from .models import ImportJob, StockMovement, StockAlert
from .services import _get_stock_status


class StockDashboardSerializer(serializers.Serializer):
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

    @extend_schema_field(OpenApiTypes.STR)
    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None


class StockAlertSerializer(serializers.ModelSerializer):
    product_sku   = serializers.CharField(source='product.sku', read_only=True)
    variant_label = serializers.SerializerMethodField()

    class Meta:
        model  = StockAlert
        fields = ['id', 'product_sku', 'variant_label', 'stock_at_alert', 'resolved', 'created_at']

    @extend_schema_field(OpenApiTypes.STR)
    def get_variant_label(self, obj):
        return obj.variant.option.label if obj.variant else None


ADJUSTMENT_REASONS = [
    'PHYSICAL_COUNT', 'LOSS', 'THEFT',
    'RETURN', 'DISCONTINUED', 'OTHER',
]


class StockAdjustSerializer(serializers.Serializer):
    delta  = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=ADJUSTMENT_REASONS, required=True)
    notes  = serializers.CharField(required=False, default='', allow_blank=True, max_length=500)

    def validate_delta(self, value):
        # H-CICLO62-02: delta=0 crearía un StockMovement sin efecto real,
        # contaminando el historial de auditoría con movimientos nulos.
        if value == 0:
            raise serializers.ValidationError(
                'El delta no puede ser cero. Usa un valor positivo (entrada) '
                'o negativo (salida/corrección).'
            )
        return value


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ImportJob
        fields = ['id', 'status', 'total_rows', 'imported_rows', 'failed_rows', 'created_at']


class VariantAdjustNewQuantitySerializer(serializers.Serializer):
    new_quantity = serializers.IntegerField(required=True)
    reason       = serializers.ChoiceField(choices=ADJUSTMENT_REASONS, required=True)
    observations = serializers.CharField(required=False, default='', allow_blank=True, max_length=500)


class RestockSerializer(serializers.Serializer):
    """Entrada de stock (UC-INV). quantity siempre positiva."""
    quantity  = serializers.IntegerField(required=True)
    reference = serializers.CharField(required=False, default='', allow_blank=True, max_length=50)
    notes     = serializers.CharField(required=False, default='', allow_blank=True, max_length=500)

    def validate_quantity(self, value):
        # UC-INV: la entrada de stock debe ser estrictamente positiva. Una
        # cantidad <= 0 no es un reabastecimiento — usar el ajuste manual
        # (UC-INV-04) para correcciones a la baja.
        if value <= 0:
            raise serializers.ValidationError(
                'La cantidad de entrada debe ser un entero positivo.'
            )
        return value
