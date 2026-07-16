"""
Serializers — ProductDiscount (UC-DASH-01..04).

DEC-DOC-005: English identifiers and English JSON keys.
"""
from decimal import Decimal
from rest_framework import serializers
from .models import Product, ProductDiscount




class ProductDiscountSerializer(serializers.ModelSerializer):
    """Read serializer — output shape consumed by the dashboard UI."""

    product_id = serializers.IntegerField(source='product.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    status = serializers.CharField(read_only=True)
    original_price = serializers.SerializerMethodField()
    discounted_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductDiscount
        fields = [
            'id', 'product_id', 'product_name',
            'discount_pct', 'valid_from', 'valid_until',
            'is_active', 'status',
            'original_price', 'discounted_price',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_original_price(self, obj) -> str:
        return str(obj.product.price)

    def get_discounted_price(self, obj) -> str:
        return str(obj.discounted_price)


class ProductDiscountCreateSerializer(serializers.Serializer):
    """POST /admin/product-discounts/ — UC-DASH-02."""

    product_id = serializers.IntegerField()
    discount_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=Decimal('0.01'), max_value=Decimal('100.00'),
    )
    valid_from = serializers.DateTimeField()
    valid_until = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        valid_until = data.get('valid_until')
        if valid_until is not None and valid_until <= data['valid_from']:
            raise serializers.ValidationError(
                {'codigo_error': 'INVALID_DATE_RANGE',
                 'detail': 'valid_until must be strictly after valid_from.'},
            )
        return data


class ProductDiscountUpdateSerializer(serializers.Serializer):
    """PATCH /admin/product-discounts/<id>/ — UC-DASH-03 (product_id immutable)."""

    discount_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=Decimal('0.01'), max_value=Decimal('100.00'),
        required=False,
    )
    valid_from = serializers.DateTimeField(required=False)
    valid_until = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        instance = self.instance
        new_from = data.get('valid_from', instance.valid_from if instance else None)
        new_until = data.get(
            'valid_until',
            instance.valid_until if instance and 'valid_until' not in data else None,
        )
        # Re-read because default may shadow None correctly
        if 'valid_until' not in data and instance is not None:
            new_until = instance.valid_until
        if new_until is not None and new_from is not None and new_until <= new_from:
            raise serializers.ValidationError(
                {'codigo_error': 'INVALID_DATE_RANGE',
                 'detail': 'valid_until must be strictly after valid_from.'},
            )
        return data
