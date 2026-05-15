"""Serializers — apps.orders (Sprint 14)."""
from decimal import Decimal
from rest_framework import serializers
from .models import Order, OrderItem, OrderValue, OrderAddress


class OrderAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderAddress
        fields = ['recipient_name','street','city','state','zip_code','country','phone']


class OrderAddressInputSerializer(serializers.Serializer):
    """Input para dirección de envío en el checkout."""
    recipient_name = serializers.CharField(max_length=200)
    street         = serializers.CharField(max_length=255)
    city           = serializers.CharField(max_length=100)
    state          = serializers.CharField(max_length=100)
    zip_code       = serializers.CharField(max_length=10)
    country        = serializers.CharField(max_length=2, default='MX')
    phone          = serializers.CharField(max_length=20, required=False, default='')


class OrderValueSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderValue
        fields = ['subtotal','tax','shipping_cost','discount','total']


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = OrderItem
        fields = ['id','product_name','variant_label','sku',
                  'unit_price','quantity','subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items   = OrderItemSerializer(many=True, read_only=True)
    value   = OrderValueSerializer(read_only=True)
    address = OrderAddressSerializer(read_only=True)
    shipping_method_name = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = ['id','order_number','status','user','guest_email',
                  'shipping_method_name','voucher_code','voucher_discount',
                  'notes','items','value','address','created_at']

    def get_shipping_method_name(self, obj):
        return obj.shipping_method.name if obj.shipping_method else None


class CheckoutSerializer(serializers.Serializer):
    """Input del checkout — UC-ORD-01."""
    cart_token         = serializers.UUIDField(required=False, allow_null=True,
                             help_text='Para visitantes anónimos.')
    guest_email        = serializers.EmailField(required=False, allow_null=True)
    address            = OrderAddressInputSerializer()
    shipping_method_id = serializers.IntegerField(required=False, allow_null=True)
    notes              = serializers.CharField(required=False, default='', allow_blank=True)
