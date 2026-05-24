"""Serializers — apps.cart (Sprint 12)."""
import uuid
from decimal import Decimal
from rest_framework import serializers
from .models import Cart, CartItem, SavedCart, SavedCartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name  = serializers.CharField(source='product.name', read_only=True)
    product_slug  = serializers.CharField(source='product.slug', read_only=True)
    variant_label = serializers.SerializerMethodField()
    sku           = serializers.SerializerMethodField()
    subtotal      = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()
    is_available  = serializers.SerializerMethodField()
    price_changed = serializers.SerializerMethodField()

    class Meta:
        model  = CartItem
        fields = [
            'id', 'product_name', 'product_slug', 'variant_label', 'sku',
            'quantity', 'unit_price', 'subtotal',
            'available_stock', 'is_available', 'price_changed',
        ]

    def get_variant_label(self, obj) -> str | None:
        return obj.variant.option.label if obj.variant else None

    def get_sku(self, obj) -> str:
        return obj.variant.sku if obj.variant else obj.product.sku

    def get_subtotal(self, obj) -> str:
        return str(obj.get_subtotal())

    def get_available_stock(self, obj) -> int:
        return obj.available_stock()

    def get_is_available(self, obj) -> bool:
        return obj.is_available()

    def get_price_changed(self, obj) -> bool:
        """True si el precio fue actualizado durante esta request (FR-CART-01.02)."""
        changed_ids = self.context.get('changed_ids', set())
        if changed_ids:
            return obj.pk in changed_ids
        # Fallback: comparar con precio vigente
        return obj.current_price() != obj.unit_price


class CartSerializer(serializers.ModelSerializer):
    items  = CartItemSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()

    class Meta:
        model  = Cart
        fields = ['id', 'cart_token', 'items', 'totals']

    def get_totals(self, obj) -> dict:
        return obj.get_totals()


class AddItemSerializer(serializers.Serializer):
    """POST /api/v1/cart/items/ — UC-CART-01."""
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity   = serializers.IntegerField(min_value=1, default=1)


class UpdateItemSerializer(serializers.Serializer):
    """PATCH /api/v1/cart/items/<pk>/ — UC-CART-02."""
    quantity = serializers.IntegerField(min_value=1)


class MergeCartSerializer(serializers.Serializer):
    """POST /api/v1/cart/merge/ — UC-CART-06."""
    cart_token = serializers.UUIDField()


class SavedCartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model  = SavedCartItem
        fields = ['id', 'product_name', 'quantity', 'price_at_save']


class SavedCartSerializer(serializers.ModelSerializer):
    items = SavedCartItemSerializer(many=True, read_only=True)

    class Meta:
        model  = SavedCart
        fields = ['id', 'items', 'created_at', 'updated_at']
