"""Serializers — addons.cart (Sprint 12 · S4 unificación cart→order→sale).

``CartItemSerializer``/``CartSerializer`` fueron retirados junto con los
modelos ``Cart``/``CartItem`` (S4): el carrito se sirve desde
``Order(DRAFT)`` con ``DraftItemSerializer``/``DraftCartSerializer``,
que preservan el contrato campo a campo.
"""
from rest_framework import serializers
from addons.orders.models import Order, OrderItem
from addons.orders.services import get_draft_totals
from .models import SavedCart, SavedCartItem


class DraftItemSerializer(serializers.ModelSerializer):
    """Línea del carrito servida desde ``orders.OrderItem`` (S2c-2b).

    Contrato IDÉNTICO a ``CartItemSerializer`` — el UI no distingue si la
    línea viene de ``cart.CartItem`` o del ``Order(DRAFT)`` (en Odoo el
    carrito ES un ``sale.order`` draft y sus líneas ``sale.order.line``).
    Diferencia interna: ``product_name``/``variant_label``/``sku`` salen del
    snapshot vivo de la línea (refrescado por los servicios del draft), y
    ``product`` es nullable (SET_NULL), por lo que los campos derivados del
    producto llevan guardia.
    """
    variant_label   = serializers.SerializerMethodField()
    product_slug    = serializers.SerializerMethodField()
    price_subtotal  = serializers.SerializerMethodField()
    price_tax       = serializers.SerializerMethodField()
    price_total     = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()
    is_available    = serializers.SerializerMethodField()
    price_changed   = serializers.SerializerMethodField()
    image_url       = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            'id', 'product_name', 'product_slug', 'variant_label', 'sku',
            'quantity', 'unit_price', 'subtotal',
            'price_subtotal', 'price_tax', 'price_total',
            'available_stock', 'is_available', 'price_changed', 'image_url',
        ]

    def get_product_slug(self, obj) -> str | None:
        return obj.product.slug if obj.product else None

    def get_variant_label(self, obj) -> str | None:
        return obj.variant_label or None

    def get_image_url(self, obj) -> str | None:
        if not obj.product:
            return None
        cover = (obj.product.images.filter(is_cover=True).first()
                 or obj.product.images.first())
        if not (cover and cover.image):
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(cover.image.url) if request else cover.image.url

    def get_price_subtotal(self, obj) -> str:
        return str(obj.price_subtotal())

    def get_price_tax(self, obj) -> str:
        return str(obj.price_tax())

    def get_price_total(self, obj) -> str:
        return str(obj.price_total())

    def get_available_stock(self, obj) -> int:
        return obj.available_stock()

    def get_is_available(self, obj) -> bool:
        return obj.is_available()

    def get_price_changed(self, obj) -> bool:
        changed_ids = self.context.get('changed_ids', set())
        if changed_ids:
            return obj.pk in changed_ids
        return obj.current_price() != obj.unit_price


class DraftCartSerializer(serializers.ModelSerializer):
    """El ``Order(DRAFT)`` presentado con el contrato de ``CartSerializer``.

    Mismas 4 claves (``id``/``cart_token``/``items``/``totals``); ``totals``
    delega en ``get_draft_totals`` (paridad de las 13 claves con
    ``Cart.get_totals``, verificada en TestDraftTotalsS2c).
    """
    items  = DraftItemSerializer(many=True, read_only=True)
    totals = serializers.SerializerMethodField()

    class Meta:
        model  = Order
        fields = ['id', 'cart_token', 'items', 'totals']

    def get_totals(self, obj) -> dict:
        return get_draft_totals(obj)


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
