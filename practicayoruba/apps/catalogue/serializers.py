"""
Serializers — apps.catalogue
Sprint 4 — UC-CAT-01
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
