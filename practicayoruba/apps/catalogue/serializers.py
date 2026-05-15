"""
Serializers — apps.catalogue

Sprint 4 — UC-CAT-01
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-CAT-03-EXT, UC-SRCH-01
Sprint 6 — UC-SRCH-02, UC-SRCH-03, UC-CAT-04, UC-CAT-05, UC-CAT-06
"""
import re
from rest_framework import serializers
from .models import Category, Product, ProductImage, SearchHistory
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
            'stock', 'is_active', 'is_published',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)

    def get_availability(self, obj) -> str:
        """UC-CAT-01: IN_STOCK si stock > 0, OUT_OF_STOCK si no."""
        return 'IN_STOCK' if obj.stock > 0 else 'OUT_OF_STOCK'


class RelatedProductSerializer(serializers.ModelSerializer):
    """UC-CAT-07 — producto relacionado mínimo para la sección al pie de ficha."""
    base_price     = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    price_with_tax = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = ['id', 'name', 'slug', 'base_price', 'price_with_tax', 'stock']

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)


class ProductDetailSerializer(serializers.ModelSerializer):
    """UC-CAT-02 — ficha completa del producto."""
    category          = CategorySerializer(read_only=True)
    base_price        = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2, read_only=True
    )
    price_with_tax    = serializers.SerializerMethodField()
    availability      = serializers.SerializerMethodField()
    images            = serializers.SerializerMethodField()
    discount          = serializers.SerializerMethodField()
    related_products  = serializers.SerializerMethodField()
    variants           = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'short_description', 'description',
            'category',
            'base_price', 'price_with_tax', 'discount',
            'stock', 'availability',
            'images',
            'related_products',
            'variants',
            'is_active', 'is_published',
            'created_at', 'updated_at',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)

    def get_availability(self, obj) -> str:
        """UC-CAT-01 / FR-CAT-01.02: IN_STOCK si stock > 0, OUT_OF_STOCK si no."""
        return 'IN_STOCK' if obj.stock > 0 else 'OUT_OF_STOCK'

    def get_images(self, obj):
        # Sprint 8: sustituir por ProductImageSerializer(obj.images.all(), many=True).data
        return []

    def get_discount(self, obj):
        # Sprint 7 (vouchers): sustituir por lógica de ProductDiscount activo (BR-012) — Sprint 13
        return None

    def get_variants(self, obj):
        """
        UC-CHT-01 (FR-CHT-01.02): variantes activas del producto.
        Incluidas en la ficha sin endpoint separado.
        """
        VariantSer = _get_variant_serializer()
        qs = (
            obj.variants.filter(is_active=True)
            .select_related('option', 'option__variant_type')
            .order_by('option__order', 'option__label')
        )
        return VariantSer(qs, many=True, context=self.context).data

    def get_related_products(self, obj):
        """
        UC-CAT-07 (FR-CAT-07.02): hasta 4 productos activos de la misma categoría,
        excluyendo el producto actual, ordenados por más reciente.
        """
        qs = (
            Product.objects
            .filter(
                category=obj.category,
                is_active=True,
                is_published=True,
            )
            .exclude(pk=obj.pk)
            .order_by('-created_at')[:4]
        )
        return RelatedProductSerializer(qs, many=True, context=self.context).data


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
            'stock',
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
    """
    UC-SRCH-03 — entrada del historial de búsquedas.
    H-INH-002: el campo interno 'updated_at' se expone como 'searched_at'
    para mantener backward compatibility con la API. drf-spectacular
    lo documenta con el nombre del campo del serializer ('searched_at').
    """
    searched_at = serializers.DateTimeField(
        source='updated_at',
        read_only=True,
        help_text='Última vez que se realizó esta búsqueda.',
    )

    class Meta:
        model  = SearchHistory
        fields = ['id', 'term', 'searched_at']


# =============================================================================
# Sprint 7 — UC-CAT-07, UC-CAT-08, UC-CAT-09, UC-CAT-10
# =============================================================================

# Sprint 9 — import lazy para evitar circular import con apps.chartsize
def _get_variant_serializer():
    from apps.chartsize.serializers import ProductVariantSerializer
    return ProductVariantSerializer

class ProductImageSerializer(serializers.ModelSerializer):
    """Imagen de producto. Gestión completa en Sprint 8."""
    class Meta:
        model  = ProductImage
        fields = ['id', 'image', 'alt_text', 'order']


class CategoryWithCountSerializer(serializers.ModelSerializer):
    """
    Nodo del árbol de categorías con product_count acumulado.
    El field product_count se inyecta desde la vista (no es property del modelo).
    UC-CAT-08 (FR-CAT-08.02).
    """
    children      = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'description', 'product_count', 'children']

    def get_children(self, obj):
        # Los hijos vienen pre-cargados desde la vista vía prefetch_related
        active_children = [c for c in obj.children.all() if c.is_active]
        return CategoryWithCountSerializer(
            active_children, many=True, context=self.context
        ).data


class ProductAdminSerializer(serializers.ModelSerializer):
    """
    Serializer de escritura para crear y editar productos (admin).
    UC-CAT-09 y UC-CAT-10.

    - 'price' se recibe como 'base_price' en la API (BR-001: precio sin IVA).
    - 'slug' es opcional: se auto-genera desde 'name' si no se envía.
    - 'images' se retorna vacío hasta Sprint 8.
    - 'price_with_tax' y 'availability' son de solo lectura.
    """
    base_price     = serializers.DecimalField(
        source='price', max_digits=10, decimal_places=2,
        min_value=0,
        help_text='Precio sin IVA. Debe ser ≥ 0 (BR-001).',
    )
    price_with_tax = serializers.SerializerMethodField(read_only=True)
    availability   = serializers.SerializerMethodField()
    category_id    = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        source='category',
    )
    images         = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'short_description', 'description',
            'category_id',
            'base_price', 'price_with_tax',
            'stock', 'availability', 'images',
            'is_published', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs     = {'slug': {'required': False, 'allow_blank': True}}


    def get_availability(self, obj) -> str:
        """UC-CAT-01: IN_STOCK si stock > 0, OUT_OF_STOCK si no."""
        return 'IN_STOCK' if obj.stock > 0 else 'OUT_OF_STOCK'

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)

    def get_images(self, obj):
        # Sprint 8: sustituir por ProductImageSerializer(obj.images.all(), many=True).data
        return []

    def validate_sku(self, value):
        """FR-CAT-09.02: SKU único (case-insensitive)."""
        qs = Product.objects.filter(sku__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Este SKU ya está en uso.')
        return value.upper()

    def validate_slug(self, value):
        """Slug único. Si vacío se genera en validate()."""
        if not value:
            return value
        qs = Product.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Este slug ya está en uso.')
        return value

    def validate(self, data):
        """Auto-generar slug desde name si no se proporcionó."""
        from django.utils.text import slugify
        if not data.get('slug') and data.get('name'):
            base_slug = slugify(data['name'])
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            data['slug'] = slug
        return data
