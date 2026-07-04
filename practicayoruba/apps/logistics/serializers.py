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
            'tracking_number', 'tracking_url', 'status', 'delivered_at',
            'estimated_delivery', 'notes', 'created_at', 'last_event',
        ]
        read_only_fields = ['delivered_at', 'created_at']

    def get_last_event(self, obj) -> dict | None:
        ev = obj.events.first()
        return ShipmentEventSerializer(ev).data if ev else None


class ShipmentGuideCreateSerializer(serializers.ModelSerializer):
    # La orden se puede identificar por su PK (order_id) o por su identificador
    # público order_number. El resto del admin usa order_number (el PK entero se
    # oculta a propósito, H-CICLO79-03), así que la UI envía order_number; se
    # mantiene order_id por compatibilidad. Ambos mapean a source='order'.
    order_id     = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), source='order', write_only=True,
        required=False,
    )
    order_number = serializers.SlugRelatedField(
        slug_field='order_number', queryset=Order.objects.all(),
        source='order', write_only=True, required=False,
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
        fields = ['order_id', 'order_number', 'courier_id', 'tracking_number', 'notes']

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
        order = attrs.get('order')
        if order is None:
            raise serializers.ValidationError({
                'detail': 'Debe indicar order_id u order_number.',
                'codigo_error': 'ORDER_REQUIRED',
            })
        # H-CICLO23-01: verificar que la orden está en estado IN_PREPARATION
        # antes de crear guía. Crear una guía para una orden PENDING/PROCESSING
        # o ya DELIVERED/CANCELLED es un error de negocio silencioso que deja
        # la orden en estado incoherente.
        if order.status != Order.STATUS_IN_PREPARATION:
            raise serializers.ValidationError({
                'detail': (
                    f'La orden debe estar en estado IN_PREPARATION para crear '
                    f'una guía de envío. Estado actual: {order.status}.'
                ),
                'codigo_error': 'ORDER_NOT_IN_PREPARATION',
            })
        if ShipmentGuide.all_objects.filter(order=order, is_deleted=False).exists():
            raise serializers.ValidationError({
                'detail': 'La orden ya tiene una guia de envio activa.',
                'codigo_error': 'SHIPMENT_GUIDE_DUPLICATE',
            })
        return attrs


class CourierCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Courier
        fields = ['name', 'code', 'tracking_url_template', 'is_active']


class BuyerShipmentGuideSerializer(serializers.ModelSerializer):
    courier_name = serializers.CharField(source='courier.name', read_only=True)
    tracking_url = serializers.SerializerMethodField()
    last_event   = serializers.SerializerMethodField()

    class Meta:
        model  = ShipmentGuide
        fields = [
            'tracking_number', 'status', 'estimated_delivery',
            'delivered_at', 'courier_name', 'tracking_url', 'last_event',
        ]
        read_only_fields = fields

    def get_tracking_url(self, obj) -> str | None:
        # UC-LOG-02 Alt B: una URL directa registrada en la guia tiene
        # precedencia sobre el template del courier.
        if obj.tracking_url:
            return obj.tracking_url
        tpl = obj.courier.tracking_url_template
        if not tpl or not obj.tracking_number:
            return None
        return tpl.replace('{tracking_number}', obj.tracking_number)

    def get_last_event(self, obj) -> dict | None:
        ev = obj.events.order_by('-occurred_at').first()
        return ShipmentEventSerializer(ev).data if ev else None
