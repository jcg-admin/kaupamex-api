"""Serializers del recorrido del comprador sobre su venta (UC-ORD-02/03/04).

Restaura el contrato que servía el addon espejo ``orders`` antes de su retiro
(SOL-098, ``api@77bd1f0``), reanclado a la venta canónica. La referencia pone
esta superficie en ``sale``: ``sale/controllers/portal.py`` expone
``/my/orders`` y ``/my/orders/<id>``, mientras el carrito y el checkout viven
en ``website_sale`` — ver ``analisis-hogar-de-g4-segun-referencia-odoo``.

**Las claves del contrato no cambian.** El consumidor sigue leyendo
``order_number``, ``items``, ``value`` y ``status``; lo que cambia es de dónde
salen: la identidad es ``SaleOrder.name``, las partidas son
``SaleOrderLine``, los importes se derivan de las líneas y el estado se
proyecta de los tres ejes. Renombrar el contrato habría roto al consumidor sin
ganar nada — el vocabulario canónico gobierna el código, no el payload.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from addons.delivery.models import DeliveryAddress

from .amounts import order_amounts
from .models import SaleOrder, SaleOrderLine
from .status_projection import STATUSES, order_status

_STATUS_LABELS = dict(STATUSES)


def _projected_status(obj) -> str:
    """Estado proyectado, memoizado por instancia.

    ``status`` y ``status_display`` lo piden en la misma serialización; sin el
    memo la proyección —que consulta pagos y guía— se derivaría dos veces por
    orden, y en un listado eso es 2N consultas.
    """
    if not hasattr(obj, '_projected_status_cache'):
        obj._projected_status_cache = order_status(obj)
    return obj._projected_status_cache


def product_lines(order):
    """Las partidas que el comprador reconoce como lo que compró.

    Excluye las líneas marcadoras ``is_delivery``/``is_reward``: envío y
    descuento son términos del total y ya viajan en ``value``, así que
    listarlas como partidas las contaría dos veces a ojos del comprador.
    """
    prefetched = getattr(order, '_product_lines_prefetched', None)
    if prefetched is not None:
        return prefetched
    return list(order.order_line
                .filter(is_delivery=False, is_reward=False)
                .select_related('product', 'variant__option')
                .order_by('id'))


class DeliveryAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeliveryAddress
        fields = ['recipient_name', 'street', 'city', 'state', 'zip_code',
                  'country', 'phone']


class OrderValueSerializer(serializers.Serializer):
    """Desglose de importes — las cinco claves históricas del contrato.

    Se serializa en vez de devolver el dict crudo porque ``order_amounts``
    entrega ``Decimal`` (es una función de dominio) y el contrato son
    **strings** con dos decimales. Devolver el ``Decimal`` degradaba el tipo a
    float en los consumidores que reserializan la respuesta.
    """
    subtotal      = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax           = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount      = serializers.DecimalField(max_digits=12, decimal_places=2)
    total         = serializers.DecimalField(max_digits=12, decimal_places=2)


class OrderItemSerializer(serializers.ModelSerializer):
    """Una partida del pedido, con los nombres externos del contrato.

    ``product_name``/``unit_price``/``quantity``/``subtotal`` son las claves
    que el consumidor ya lee; en la canónica viven en ``name``/``price_unit``/
    ``product_uom_qty`` y en el método ``price_total()``.
    """
    product_name  = serializers.CharField(source='name', read_only=True)
    variant_label = serializers.SerializerMethodField()
    sku           = serializers.SerializerMethodField()
    unit_price    = serializers.DecimalField(
        source='price_unit', max_digits=12, decimal_places=2, read_only=True)
    quantity      = serializers.IntegerField(
        source='product_uom_qty', read_only=True)
    subtotal      = serializers.SerializerMethodField()
    image_url     = serializers.SerializerMethodField()

    class Meta:
        model  = SaleOrderLine
        fields = ['id', 'product_name', 'variant_label', 'sku',
                  'unit_price', 'quantity', 'subtotal', 'image_url']

    def get_variant_label(self, obj) -> str:
        return obj.variant.option.label if obj.variant_id else ''

    def get_sku(self, obj) -> str:
        return obj.product.sku if obj.product_id else ''

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_subtotal(self, obj):
        # Bruto de la línea (IVA incluido, como el precio de catálogo): la suma
        # de las partidas tiene que cuadrar con el total que el comprador pagó.
        return obj.price_total()

    @extend_schema_field(OpenApiTypes.URI)
    def get_image_url(self, obj) -> str | None:
        # El producto es FK nullable (SET_NULL si se eliminó del catálogo); en
        # ese caso el consumidor cae a su placeholder.
        if not obj.product_id:
            return None
        cover = (obj.product.images.filter(is_cover=True).first()
                 or obj.product.images.first())
        if not (cover and cover.image):
            return None
        request = self.context.get('request')
        return (request.build_absolute_uri(cover.image.url) if request
                else cover.image.url)


class OrderSerializer(serializers.ModelSerializer):
    """Detalle completo de una orden — UC-ORD-02."""
    order_number         = serializers.CharField(source='name', read_only=True)
    user                 = serializers.PrimaryKeyRelatedField(
        source='partner', read_only=True)
    items                = serializers.SerializerMethodField()
    value                = serializers.SerializerMethodField()
    address              = DeliveryAddressSerializer(
        source='delivery_address', read_only=True)
    shipping_method_name = serializers.SerializerMethodField()
    status               = serializers.SerializerMethodField()
    status_display       = serializers.SerializerMethodField()

    class Meta:
        model  = SaleOrder
        # Sin ``id``: el PK entero es secuencial y permitiría enumerar las
        # órdenes del sistema. ``order_number`` es el identificador público.
        fields = [
            'order_number', 'status', 'status_display',
            'user', 'guest_email', 'shipping_method_name', 'notes',
            'items', 'value', 'address',
            'created_at', 'cancelled_at', 'cancellation_reason',
        ]

    @extend_schema_field(OrderItemSerializer(many=True))
    def get_items(self, obj):
        return OrderItemSerializer(product_lines(obj), many=True,
                                   context=self.context).data

    @extend_schema_field(OrderValueSerializer)
    def get_value(self, obj) -> dict:
        return OrderValueSerializer(order_amounts(obj)).data

    def get_shipping_method_name(self, obj) -> str | None:
        return obj.carrier.name if obj.carrier_id else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_status(self, obj) -> str:
        return _projected_status(obj)

    def get_status_display(self, obj) -> str:
        projected = _projected_status(obj)
        return _STATUS_LABELS.get(projected, projected)


class OrderListSerializer(serializers.ModelSerializer):
    """Resumen para el historial — UC-ORD-03."""
    order_number   = serializers.CharField(source='name', read_only=True)
    total          = serializers.DecimalField(
        source='amount_total', max_digits=12, decimal_places=2, read_only=True)
    items_count    = serializers.SerializerMethodField()
    thumbnail_url  = serializers.SerializerMethodField()
    status         = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model  = SaleOrder
        fields = ['order_number', 'status', 'status_display',
                  'created_at', 'updated_at', 'total', 'items_count',
                  'thumbnail_url']

    @extend_schema_field(OpenApiTypes.INT)
    def get_items_count(self, obj):
        return len(product_lines(obj))

    @extend_schema_field(OpenApiTypes.URI)
    def get_thumbnail_url(self, obj) -> str | None:
        lines = product_lines(obj)
        if not lines:
            return None
        product = getattr(lines[0], 'product', None)
        if product is None:
            return None
        cover = (product.images.filter(is_cover=True).first()
                 or product.images.first())
        if not (cover and cover.image):
            return None
        request = self.context.get('request')
        return (request.build_absolute_uri(cover.image.url) if request
                else cover.image.url)

    @extend_schema_field(OpenApiTypes.STR)
    def get_status(self, obj) -> str:
        return _projected_status(obj)

    def get_status_display(self, obj) -> str:
        projected = _projected_status(obj)
        return _STATUS_LABELS.get(projected, projected)


class CancelOrderSerializer(serializers.Serializer):
    """Cuerpo de POST ``/api/v2/orders/<order_number>/cancellations/``."""
    reason = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=500,
        help_text='Motivo de la cancelación (opcional, visible al comprador).',
    )
