"""
Serializers — apps.chartsize

Sprint 9 — UC-CHT-01, UC-CHT-03, UC-CHT-04
"""
from decimal import Decimal
from rest_framework import serializers
from apps.settings_app.models import SiteSettings
from .models import VariantType, VariantOption, ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Variante para el visitante (lectura). UC-CHT-01 (FR-CHT-01.02).
    Incluida dentro de ProductDetailSerializer como campo 'variants'.
    """
    label          = serializers.CharField(source='option.label', read_only=True)
    slug           = serializers.CharField(source='option.slug',  read_only=True)
    effective_price = serializers.SerializerMethodField()
    price_with_tax  = serializers.SerializerMethodField()
    is_available    = serializers.SerializerMethodField()

    class Meta:
        model  = ProductVariant
        fields = [
            'id', 'label', 'slug', 'sku_suffix',
            'stock', 'is_available',
            'effective_price', 'price_with_tax',
        ]

    def get_effective_price(self, obj) -> str:
        return str(obj.effective_price())

    def get_price_with_tax(self, obj) -> float:
        iva = SiteSettings.get_current().iva_rate
        return round(float(obj.effective_price()) * (1 + float(iva)), 2)

    def get_is_available(self, obj) -> bool:
        return obj.is_available()


class VariantOptionAdminSerializer(serializers.ModelSerializer):
    """Opcion de variante para el admin."""
    class Meta:
        model  = VariantOption
        fields = ['id', 'label', 'slug', 'is_active', 'order']
        extra_kwargs = {'slug': {'required': False, 'allow_blank': True}}


class VariantTypeAdminSerializer(serializers.ModelSerializer):
    """Tipo de variante con sus opciones para el admin."""
    options = VariantOptionAdminSerializer(many=True, read_only=True)

    class Meta:
        model  = VariantType
        fields = ['id', 'name', 'is_active', 'order', 'options']

    def validate_name(self, value):
        product = self.context.get('product')
        if not product:
            return value
        qs = VariantType.objects.filter(product=product, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f'Este producto ya tiene un tipo de variante llamado "{value}".'
            )
        return value


class ProductVariantAdminSerializer(serializers.ModelSerializer):
    """
    Variante completa para el admin (lectura y escritura).
    UC-CHT-03 y UC-CHT-04.
    """
    label           = serializers.CharField(source='option.label', read_only=True)
    slug            = serializers.CharField(source='option.slug',  read_only=True)
    effective_price = serializers.SerializerMethodField()
    price_with_tax  = serializers.SerializerMethodField()

    class Meta:
        model  = ProductVariant
        fields = [
            'id', 'label', 'slug', 'sku_suffix',
            'price_override', 'effective_price', 'price_with_tax',
            'stock', 'is_active',
        ]

    def get_effective_price(self, obj) -> str:
        return str(obj.effective_price())

    def get_price_with_tax(self, obj) -> float:
        iva = SiteSettings.get_current().iva_rate
        return round(float(obj.effective_price()) * (1 + float(iva)), 2)

    def validate_price_override(self, value):
        """FR-CHT-04.02: precio diferenciado debe ser > 0 (no 0, no negativo)."""
        if value is not None and value <= Decimal('0'):
            raise serializers.ValidationError(
                'El precio diferenciado debe ser mayor que cero.'
            )
        return value
