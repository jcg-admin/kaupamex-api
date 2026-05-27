"""Serializers — apps.orders (Sprint 14)."""
from decimal import Decimal
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import Order, OrderItem, OrderValue, OrderAddress, ShippingZone, OrderStatusLog


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
    """Detalle completo de una orden — UC-ORD-02."""
    items                = OrderItemSerializer(many=True, read_only=True)
    value                = OrderValueSerializer(read_only=True)
    address              = OrderAddressSerializer(read_only=True)
    shipping_method_name = serializers.SerializerMethodField()
    status_display       = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        # H-CICLO79-03: 'id' eliminado. El PK entero auto-incremental
        # es secuencial y permite enumerar todas las ordenes del sistema
        # (viola la convencion de no exponer PKs a compradores, aplicada
        # tambien en H-CICLO76-01 para payments). 'order_number' (UUID-
        # derivado, no secuencial) es el identificador publico correcto
        # y ya es el unico campo que usan las rutas y el frontend.
        fields = [
            'order_number', 'status', 'status_display',
            'user', 'guest_email', 'shipping_method_name',
            'voucher_code', 'voucher_discount', 'notes',
            'items', 'value', 'address',
            'created_at', 'cancelled_at', 'cancellation_reason',
        ]

    def get_shipping_method_name(self, obj) -> str | None:
        return obj.shipping_method.name if obj.shipping_method else None

    def get_status_display(self, obj) -> str:
        return obj.get_status_display()


class OrderStatusLogSerializer(serializers.ModelSerializer):
    """H-CICLO101-API-01: expose status_logs in AdminOrderSerializer so the
    admin panel can display the full state-transition audit trail."""
    changed_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = OrderStatusLog
        fields = [
            'id', 'previous_status', 'new_status', 'notes',
            'changed_by_username', 'created_at',
        ]

    def get_changed_by_username(self, obj) -> str | None:
        return obj.changed_by.username if obj.changed_by_id else None


class AdminOrderSerializer(OrderSerializer):
    """UC-ORD-09 (DEC-AOQ-02): subclass para vistas admin que expone
    user_email + user_username derivados del FK. La UI admin antes
    consumia ``order.user?.email`` -> undefined porque ``user`` era
    PK entero. Reuso del patron de AdminReturnListSerializer (returns)
    sin tocar OrderSerializer base usado por endpoints buyer.

    H-CICLO101-API-01: agrega status_logs para que el panel admin
    muestre el historial de transiciones de estado de la orden."""

    user_email    = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    # H-CICLO101-API-01: status_logs exposes the full state-transition
    # audit trail.  AdminOrderDetailView already prefetch_related(
    # 'status_logs__changed_by') so no extra queries are added here.
    status_logs   = OrderStatusLogSerializer(many=True, read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + [
            'user_email', 'user_username', 'status_logs',
        ]

    def get_user_email(self, obj) -> str | None:
        return obj.user.email if obj.user_id else None

    def get_user_username(self, obj) -> str | None:
        return obj.user.username if obj.user_id else None


class OrderListSerializer(serializers.ModelSerializer):
    """Resumen de orden para el listado — UC-ORD-03 (FR-ORD-03.02)."""
    total         = serializers.DecimalField(
        source='value.total', max_digits=10, decimal_places=2, read_only=True,
    )
    items_count   = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = [
            'order_number', 'status', 'status_display',
            'created_at', 'updated_at', 'total', 'items_count', 'thumbnail_url',
        ]

    def get_items_count(self, obj):
        # Evitar N+1: usa _items_prefetched si está disponible
        items = getattr(obj, '_items_prefetched', None)
        if items is not None:
            return len(items)
        return obj.items.count()

    def get_thumbnail_url(self, obj):
        # H-ORD-003: imagen del primer item, resuelta en tiempo de consulta
        items = getattr(obj, '_items_prefetched', None) or list(obj.items.all())
        if not items:
            return None
        first_item = items[0]
        product = getattr(first_item, 'product', None)
        if not product:
            return None
        images = getattr(product, '_images_prefetched', None)
        if images is None:
            images = list(product.images.filter(is_cover=True)[:1])
        cover = images[0] if images else None
        if not cover:
            images_all = getattr(product, '_all_images', None)
            if images_all is None:
                images_all = list(product.images.all()[:1])
            cover = images_all[0] if images_all else None
        if cover and cover.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(cover.image.url)
            return cover.image.url
        return None

    def get_status_display(self, obj) -> str:
        return obj.get_status_display()


class CheckoutSerializer(serializers.Serializer):
    """Input del checkout — UC-ORD-01."""
    cart_token         = serializers.UUIDField(required=False, allow_null=True,
                             help_text='Para visitantes anónimos.')
    guest_email        = serializers.EmailField(required=False, allow_null=True)
    address            = OrderAddressInputSerializer()
    shipping_method_id = serializers.IntegerField(required=False, allow_null=True)
    notes              = serializers.CharField(required=False, default='', allow_blank=True, max_length=1000)

    def validate_address(self, value):
        """DEC-BC-18: reject zip_code not covered by any active ShippingZone."""
        zip_code = value.get('zip_code', '')
        prefixes = list(
            ShippingZone.objects.filter(is_active=True)
            .values_list('zip_code_prefix', flat=True)
        )
        if not any(zip_code.startswith(p) for p in prefixes):
            raise ValidationError({
                'zip_code': 'El código postal no está cubierto por ninguna zona de envío.',
                'error_code': 'ZONE_NOT_COVERED',
            })
        return value


# ─── Sprint 18 — serializers de edición ────────────────────────────────────────────

class CancelOrderSerializer(serializers.Serializer):
    """POST /api/v1/orders/<order_number>/cancel/ — UC-ORD-04."""
    reason = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=500,
        help_text='Motivo de la cancelación (opcional, visible al comprador).',
    )


class UpdateAddressSerializer(serializers.Serializer):
    """PATCH /api/v1/orders/<order_number>/address/ — UC-ORD-05."""
    recipient_name = serializers.CharField(max_length=200)
    street         = serializers.CharField(max_length=255)
    city           = serializers.CharField(max_length=100)
    state          = serializers.CharField(max_length=100)
    zip_code       = serializers.CharField(max_length=10)
    country        = serializers.CharField(max_length=2, default='MX')
    phone          = serializers.CharField(max_length=20, required=False, default='')


class UpdateShippingSerializer(serializers.Serializer):
    """PATCH /api/v1/orders/<order_number>/shipping/ — UC-ORD-06."""
    shipping_method_id = serializers.IntegerField(
        help_text='ID del nuevo método de envío activo.',
    )
