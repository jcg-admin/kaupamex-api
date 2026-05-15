"""
Serializers — apps.catalogue

Sprint 4 — UC-CAT-01
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-CAT-03-EXT, UC-SRCH-01
Sprint 6 — UC-SRCH-02, UC-SRCH-03, UC-CAT-04, UC-CAT-05, UC-CAT-06
"""
import re
from rest_framework import serializers
from .models import Category, Product, SearchHistory
from apps.settings_app.models import SiteSettings


# =============================================================================
# Categorias
# =============================================================================

class CategorySerializer(serializers.ModelSerializer):
    """Listado público de categorías. UC-CAT-08."""
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug']


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Árbol de categorías con hijos anidados. UC-CAT-08."""
    children = serializers.SerializerMethodField()

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'description', 'children']

    def get_children(self, obj):
        active_children = obj.children.filter(is_active=True)
        return CategoryTreeSerializer(active_children, many=True).data


class CategoryAdminSerializer(serializers.ModelSerializer):
    """
    CRUD de categorías para el administrador. UC-CAT-06.
    Incluye validación de ciclos en la jerarquía (FR-CAT-06.02).
    """
    parent_id   = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        source='parent', required=False, allow_null=True,
    )
    product_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = Category
        fields = [
            'id', 'name', 'slug', 'description',
            'parent_id', 'is_active', 'product_count',
        ]

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()

    def validate(self, data):
        """FR-CAT-06.02: detectar ciclos antes de persistir."""
        parent = data.get('parent', self.instance.parent if self.instance else None)
        instance = self.instance
        if instance and parent is not None:
            if instance.would_create_cycle(parent):
                raise serializers.ValidationError({
                    'parent_id': 'Esta relacion crearia un ciclo en la jerarquia de categorias.',
                    'codigo_error': 'CICLO_EN_JERARQUIA',
                })
        return data

    def validate_name(self, value):
        qs = Category.objects.filter(name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe una categoria con ese nombre.')
        return value


# =============================================================================
# Productos
# =============================================================================

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
    images         = serializers.SerializerMethodField()
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
        # Sprint 7: sustituir por ProductImageSerializer
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
        term = self.context.get('search_term', '')
        if not term:
            return obj.name
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        return pattern.sub(lambda m: f'<mark>{m.group()}</mark>', obj.name)


class AutocompleteSerializer(serializers.ModelSerializer):
    """UC-SRCH-02 — sugerencia mínima para el dropdown."""
    class Meta:
        model  = Product
        fields = ['id', 'name', 'slug']


# =============================================================================
# Historial de búsquedas
# =============================================================================

class SearchHistorySerializer(serializers.ModelSerializer):
    """UC-SRCH-03 — entrada del historial de búsquedas."""
    class Meta:
        model  = SearchHistory
        fields = ['id', 'term', 'searched_at']
