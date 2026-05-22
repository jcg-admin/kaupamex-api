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


# ─── UC-INV-04 contrato UI: ajuste por nueva cantidad absoluta ─────────────
# Reason enum tomado de UC-INV-04 PARTE 7. observations es libre.
ADJUSTMENT_REASONS = [
    'CONTEO_FISICO', 'MERMA', 'ROBO',  # canon-idioma: T-709 data migration pendiente
    'DEVOLUCION', 'DESCONTINUADO', 'OTRO',  # canon-idioma: T-709 data migration pendiente
]


class VariantAdjustNewQuantitySerializer(serializers.Serializer):
    """
    UC-INV-04 — payload de la UI (UC-INV-01..05 ui agent).

    Campos en snake_case inglés; los valores del enum reason permanecen en
    español para coincidir con el catálogo de motivos visible al usuario
    final (DEC-DOC-005: identificadores en inglés, valores de negocio que el
    usuario lee pueden ser en español).
    """
    # No usamos min_value: la regla "no negativo" se aplica en la vista
    # para devolver HTTP 422 con codigo_error STOCK_NEGATIVO_NO_PERMITIDO
    # (UC-INV-04 PARTE 7), en lugar del 400 genérico de DRF.
    new_quantity = serializers.IntegerField(required=True)
    reason       = serializers.ChoiceField(choices=ADJUSTMENT_REASONS, required=True)
    observations = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=500,
    )
