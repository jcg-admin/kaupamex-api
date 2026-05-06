"""
Serializers — apps.catalogue
Sprint 4 — UC-CAT-01
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-CAT-03-EXT, UC-SRCH-01
"""
import re
from rest_framework import serializers
from .models import Category, Product
from apps.settings_app.models import SiteSettings


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug']


class ProductListSerializer(serializers.ModelSerializer):
    """UC-CAT-01 — tarjeta de producto para el listado."""
    category_name  = serializers.CharField(source='category.name', read_only=True)
    base_price     = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    price_with_tax = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'category_name',
            'base_price', 'price_with_tax',
            'stock', 'is_active', 'is_published', 'is_featured',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)


class ProductDetailSerializer(serializers.ModelSerializer):
    """UC-CAT-02 — ficha completa del producto."""
    category       = CategorySerializer(read_only=True)
    base_price     = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    price_with_tax = serializers.SerializerMethodField()
    availability   = serializers.CharField(read_only=True)
    # images: delegado a Sprint 7 (modelo ProductImage)
    images         = serializers.SerializerMethodField()
    # discount: delegado a Sprint 7 (modelo ProductDiscount)
    discount       = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'short_description', 'description',
            'category',
            'base_price', 'price_with_tax', 'discount',
            'stock', 'availability',
            'images',
            'is_active', 'is_published', 'is_featured',
            'created_at', 'updated_at',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)

    def get_images(self, obj):
        # Sprint 7: sustituir por ProductImageSerializer(obj.images.all(), many=True).data
        return []

    def get_discount(self, obj):
        # Sprint 7: sustituir por lógica de ProductDiscount activo (BR-012)
        return None


class ProductSearchSerializer(serializers.ModelSerializer):
    """UC-CAT-03 / UC-SRCH-01 — resultado de búsqueda con highlighted_name."""
    category_name   = serializers.CharField(source='category.name', read_only=True)
    base_price      = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    price_with_tax  = serializers.SerializerMethodField()
    highlighted_name = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'short_description',
            'category_name',
            'base_price', 'price_with_tax',
            'stock', 'is_featured',
            'highlighted_name',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)

    def get_highlighted_name(self, obj):
        """
        Marca el término buscado en el nombre del producto.
        Ejemplo: "Collar <mark>Oshun</mark> dorado"
        El término se pasa via context['search_term'] desde la view.
        FR-CAT-03.02: highlighted_term visible en resultados.
        """
        term = self.context.get('search_term', '')
        if not term:
            return obj.name
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        return pattern.sub(lambda m: f'<mark>{m.group()}</mark>', obj.name)
