"""
Serializers — addons.delivery (P-13).

English JSON keys per DEC-DOC-005. Business error codes Spanish per
DEC-DOC-006 — raised in views, not here.
"""
from decimal import Decimal
from rest_framework import serializers
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from .models import (
    Courier, ShipmentEvent, ShipmentGuide, ShippingMethod, ShippingZone,
)




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
    # I2 (H-API-31): la identidad se lee de la canónica — tras E4-pre la FK
    # espejo es nullable y tras I1 ambas portan el mismo valor (sale.name).
    order_number = serializers.CharField(source='sale_order.name', read_only=True)
    last_event   = serializers.SerializerMethodField()

    class Meta:
        model  = ShipmentGuide
        fields = [
            'id', 'sale_order', 'order_number', 'courier', 'courier_id',
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
    # mantiene order_id por compatibilidad. Ambos mapean a source='sale_order'.
    #
    # SOL-098 (G7): tras el retiro del espejo `orders` la canónica ES la venta;
    # el destino es `sale_order` y su identificador público es `SaleOrder.name`
    # (el espejo lo llamaba `order_number`). El NOMBRE EXTERNO del campo se
    # conserva (`order_number`) para no romper el contrato de la UI — sólo
    # cambian `source`/`slug_field`, que son internos.
    order_id     = serializers.PrimaryKeyRelatedField(
        queryset=SaleOrder.objects.all(), source='sale_order', write_only=True,
        required=False,
    )
    order_number = serializers.SlugRelatedField(
        slug_field='name', queryset=SaleOrder.objects.all(),
        source='sale_order', write_only=True, required=False,
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
        sale_order = attrs.get('sale_order')
        if sale_order is None:
            raise serializers.ValidationError({
                'detail': 'Debe indicar order_id u order_number.',
                'codigo_error': 'ORDER_REQUIRED',
            })
        # H-CICLO23-01: verificar que la orden está lista para surtir antes de
        # crear guía. Cut-over orders→sale (ADR-024): "lista para surtir" ya
        # NO se lee del enum legacy SaleOrder.status — IN_PREPARATION es un valor
        # muerto (ningún escritor canónico lo produce, H-API-10) proyectado
        # desde los ejes. Se deriva de la canónica: la orden debe estar
        # confirmada (sale.state='sale') y pagada (un Payment APPROVED). El
        # check de guía duplicada que sigue cubre "aún sin enviar".
        # La canónica ES la venta: ya no hay indirección `order.sale_order`.
        lista_para_surtir = (
            sale_order.state == SaleOrder.STATE_SALE
            and sale_order.payments.filter(
                status=Payment.STATUS_APPROVED).exists()
        )
        if not lista_para_surtir:
            raise serializers.ValidationError({
                'detail': (
                    'La orden debe estar confirmada y pagada para crear una '
                    'guía de envío.'
                ),
                'codigo_error': 'ORDER_NOT_IN_PREPARATION',
            })
        if ShipmentGuide.all_objects.filter(
                sale_order=sale_order, is_deleted=False).exists():
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


# ── Motor de cotización de paqueterías (addons.delivery.offers) ──────────────

class ShipmentPackageInputSerializer(serializers.Serializer):
    """Un paquete del envío. Dimensiones en cm, peso en kg, valor en la moneda
    de la tienda. Todos > 0; ``hazardous`` opcional (default False)."""
    length    = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal('0.01'))
    width     = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal('0.01'))
    height    = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal('0.01'))
    weight    = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal('0.01'))
    value     = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))
    hazardous = serializers.BooleanField(required=False, default=False)


class ShipmentOfferRequestSerializer(serializers.Serializer):
    """Solicitud de cotización: contacto/direcciones opcionales + paquetes."""
    contact_name     = serializers.CharField(required=False, allow_blank=True, max_length=120)
    contact_phone    = serializers.CharField(required=False, allow_blank=True, max_length=20)
    contact_email    = serializers.EmailField(required=False, allow_blank=True)
    pickup_address   = serializers.CharField(required=False, allow_blank=True, max_length=255)
    delivery_address = serializers.CharField(required=False, allow_blank=True, max_length=255)
    packages = ShipmentPackageInputSerializer(many=True, allow_empty=False)


class ShippingMethodPublicSerializer(serializers.ModelSerializer):
    """Catálogo público de métodos de envío (GAP-C1).

    Sólo lectura y sólo los campos que el checkout anónimo necesita para
    decidir: nombre, costo, umbral de gratuidad y días estimados. No expone
    ``zones`` ni el producto de servicio — son detalle interno de facturación.
    """

    class Meta:
        model  = ShippingMethod
        fields = ['id', 'name', 'cost', 'estimated_days', 'free_threshold']


class ShippingZonePublicSerializer(serializers.ModelSerializer):
    """Catálogo público de zonas y su ventana de entrega (H-12)."""

    class Meta:
        model  = ShippingZone
        fields = ['id', 'name', 'zip_code_prefix', 'estimated_days_min',
                  'estimated_days_max', 'cost', 'free_threshold']
