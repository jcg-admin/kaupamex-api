"""
Serializers — apps.logistics (P-13).

English JSON keys per DEC-DOC-005. Business error codes Spanish per
DEC-DOC-006 — raised in views, not here.
"""
from rest_framework import serializers
from apps.orders.models import Order
from .models import Courier, ShipmentEvent, ShipmentGuide




class CourierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Courier
        fields = ['id', 'name', 'code', 'tracking_url_template', 'is_active']


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ShipmentEvent
        fields = ['id', 'status', 'description', 'occurred_at', 'created_at']


class ShipmentGuideSerializer(serializers.ModelSerializer):
    courier      = CourierSerializer(read_only=True)
    courier_id   = serializers.PrimaryKeyRelatedField(
        queryset=Courier.objects.filter(is_active=True),
        source='courier', write_only=True,
    )
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    last_event   = serializers.SerializerMethodField()

    class Meta:
        model  = ShipmentGuide
        fields = [
            'id', 'order', 'order_number', 'courier', 'courier_id',
            'tracking_number', 'status', 'delivered_at', 'notes',
            'created_at', 'last_event',
        ]
        read_only_fields = ['delivered_at', 'created_at']

    def get_last_event(self, obj) -> dict | None:
        ev = obj.events.first()
        return ShipmentEventSerializer(ev).data if ev else None


class ShipmentGuideCreateSerializer(serializers.ModelSerializer):
    order_id   = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), source='order', write_only=True,
    )
    courier_id = serializers.PrimaryKeyRelatedField(
        queryset=Courier.objects.filter(is_active=True),
        source='courier', write_only=True,
    )
    # Override field to drop the auto UniqueValidator — we raise a loud
    # business error (TRACKING_DUPLICATE) ourselves in validate_tracking_number.
    tracking_number = serializers.CharField(max_length=80, validators=[])

    class Meta:
        model  = ShipmentGuide
        fields = ['order_id', 'courier_id', 'tracking_number', 'notes']

    def validate_tracking_number(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError({
                'detail': 'tracking_number requerido.',
                'codigo_error': 'TRACKING_REQUIRED',
            })
        if ShipmentGuide.all_objects.filter(tracking_number=value).exists():
            raise serializers.ValidationError({
                'detail': 'Tracking number ya registrado.',
                'codigo_error': 'TRACKING_DUPLICATE',
            })
        return value

    def validate(self, attrs):
        order = attrs['order']
        if ShipmentGuide.all_objects.filter(order=order, is_deleted=False).exists():
            raise serializers.ValidationError({
                'detail': 'La orden ya tiene una guia de envio activa.',
                'codigo_error': 'SHIPMENT_GUIDE_DUPLICATE',
            })
        return attrs
