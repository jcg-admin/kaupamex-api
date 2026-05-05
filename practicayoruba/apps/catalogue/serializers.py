"""
Serializers — apps.catalogue
Sprint 4 — UC-CAT-01
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-SRCH-01
"""
from rest_framework import serializers
from .models import Category, Product
from apps.settings_app.models import SiteSettings


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug']


class ProductListSerializer(serializers.ModelSerializer):
    category_name  = serializers.CharField(source='category.name', read_only=True)
    price_with_tax = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'category_name', 'price', 'price_with_tax',
            'stock', 'is_active', 'is_published',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)


class ProductDetailSerializer(serializers.ModelSerializer):
    """UC-CAT-02 — ficha completa del producto."""
    category       = CategorySerializer(read_only=True)
    price_with_tax = serializers.SerializerMethodField()
    availability   = serializers.CharField(read_only=True)

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'short_description', 'description',
            'category',
            'price', 'price_with_tax',
            'stock', 'availability',
            'is_active', 'is_published',
            'created_at', 'updated_at',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)


class ProductSearchSerializer(serializers.ModelSerializer):
    """UC-CAT-03 / UC-SRCH-01 — resultado de búsqueda."""
    category_name  = serializers.CharField(source='category.name', read_only=True)
    price_with_tax = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = [
            'id', 'name', 'slug', 'sku',
            'short_description',
            'category_name',
            'price', 'price_with_tax',
            'stock',
        ]

    def get_price_with_tax(self, obj):
        iva_rate = SiteSettings.get_current().iva_rate
        return round(float(obj.price) * (1 + float(iva_rate)), 2)
