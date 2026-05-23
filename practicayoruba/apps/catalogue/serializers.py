"""
Serializers — apps.catalogue

ProductListSerializer: para listas compactas (index, search results).
ProductDetailSerializer: para el detalle completo de un producto.
ProductSearchSerializer: para el endpoint de búsqueda avanzada.
CategoryWithCountSerializer: para el árbol de categorías con conteo.
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from .models import Category, Product, ProductImage, ProductDiscount, SearchHistory


def _get_sale_price(product):
    """Return discounted price string if an active discount exists, else None."""
    now = timezone.now()
    discount = (
        ProductDiscount.objects
        .filter(
            product=product,
            is_active=True,
            valid_from__lte=now,
        )
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=now))
        .order_by('-created_at')
        .first()
    )
    return str(discount.discounted_price) if discount else None




class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model  = ProductImage
        fields = ['id', 'image_url', 'alt_text', 'is_cover', 'order']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url if obj.image else None


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'parent']


class ProductListSerializer(serializers.ModelSerializer):
    """
    Campos mínimos para listas: id, name, slug, price, cover image.
    """
    cover_image_url = serializers.SerializerMethodField()
    category_name   = serializers.CharField(source='category.name', read_only=True)
    sale_price      = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'price', 'sale_price',
            'category_name', 'cover_image_url',
            'is_active', 'is_published',
        ]

    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    def get_cover_image_url(self, obj):
        request = self.context.get('request')
        cover = obj.images.filter(is_cover=True).first()
        if not cover:
            cover = obj.images.first()
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    images     = ProductImageSerializer(many=True, read_only=True)
    category   = CategorySerializer(read_only=True)
    sale_price = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'sale_price',
            'category', 'images', 'is_active', 'is_published',
            'created_at', 'updated_at',
        ]

    def get_sale_price(self, obj):
        return _get_sale_price(obj)


class ProductSearchSerializer(serializers.ModelSerializer):
    """
    Para el endpoint de búsqueda avanzada — mismo shape que ProductListSerializer
    más campos de relevancia.
    """
    cover_image_url = serializers.SerializerMethodField()
    category_name   = serializers.CharField(source='category.name', read_only=True)
    sale_price      = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'price', 'sale_price',
            'category_name', 'cover_image_url',
        ]

    def get_sale_price(self, obj):
        return _get_sale_price(obj)

    def get_cover_image_url(self, obj):
        request = self.context.get('request')
        cover = obj.images.filter(is_cover=True).first()
        if not cover:
            cover = obj.images.first()
        if cover and cover.image:
            return request.build_absolute_uri(cover.image.url) if request else cover.image.url
        return None


class CategoryWithCountSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    children      = serializers.SerializerMethodField()

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'parent', 'product_count', 'children']

    def get_product_count(self, obj):
        return obj.products.filter(is_active=True, is_published=True).count()

    def get_children(self, obj):
        children = obj.children.all()
        return CategoryWithCountSerializer(children, many=True).data


class ProductAdminSerializer(serializers.ModelSerializer):
    """Serializer completo para vistas admin — incluye campos de publicación."""
    images     = ProductImageSerializer(many=True, read_only=True)
    category   = CategorySerializer(read_only=True)
    sale_price = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'sale_price',
            'category', 'images', 'is_active', 'is_published',
            'created_at', 'updated_at',
        ]

    def get_sale_price(self, obj):
        return _get_sale_price(obj)


class AutocompleteSerializer(serializers.ModelSerializer):
    """UC-SRCH-02: sugerencias de autocomplete por prefijo."""

    class Meta:
        model  = Product
        fields = ['id', 'name', 'slug']


class SearchHistorySerializer(serializers.ModelSerializer):
    """UC-SRCH-03: historial de busquedas del comprador."""
    searched_at = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model  = SearchHistory
        fields = ['id', 'term', 'searched_at']


class CategoryAdminSerializer(serializers.ModelSerializer):
    """UC-CAT-06: administracion de categorias (admin CRUD)."""

    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'image', 'is_active']
        extra_kwargs = {'slug': {'required': False}}
