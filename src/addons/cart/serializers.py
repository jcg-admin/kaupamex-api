"""Serializers — addons.cart (Sprint 12 · S4 unificación cart→order→sale).

``CartItemSerializer``/``CartSerializer`` fueron retirados junto con los
modelos ``Cart``/``CartItem`` (S4): el carrito se sirve desde
``Order(DRAFT)`` con ``DraftItemSerializer``/``DraftCartSerializer``,
que preservan el contrato campo a campo.
"""
from decimal import Decimal
from rest_framework import serializers
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.services import get_draft_totals
from .models import SavedCart, SavedCartItem


class DraftItemSerializer(serializers.ModelSerializer):
    """Línea del carrito servida desde ``sale.SaleOrderLine`` (V2
    unificación orders→sale).

    Contrato IDÉNTICO al histórico ``CartItemSerializer`` (15 claves) — el
    UI no distingue el origen. Mapeo interno al vocabulario Odoo:
    ``quantity``←``product_uom_qty``, ``unit_price``←``price_unit``;
    ``product_name``/``sku``/``variant_label`` se derivan de la línea y sus
    FKs PROTECT (el producto no puede borrarse en duro con líneas vivas).
    """
    product_name    = serializers.SerializerMethodField()
    variant_label   = serializers.SerializerMethodField()
    product_slug    = serializers.SerializerMethodField()
    sku             = serializers.SerializerMethodField()
    quantity        = serializers.IntegerField(source='product_uom_qty',
                                               read_only=True)
    unit_price      = serializers.DecimalField(source='price_unit',
                                               max_digits=12,
                                               decimal_places=2,
                                               read_only=True)
    subtotal        = serializers.SerializerMethodField()
    price_subtotal  = serializers.SerializerMethodField()
    price_tax       = serializers.SerializerMethodField()
    price_total     = serializers.SerializerMethodField()
    available_stock = serializers.SerializerMethodField()
    is_available    = serializers.SerializerMethodField()
    price_changed   = serializers.SerializerMethodField()
    image_url       = serializers.SerializerMethodField()

    class Meta:
        model  = SaleOrderLine
        fields = [
            'id', 'product_name', 'product_slug', 'variant_label', 'sku',
            'quantity', 'unit_price', 'subtotal',
            'price_subtotal', 'price_tax', 'price_total',
            'available_stock', 'is_available', 'price_changed', 'image_url',
        ]

    def get_product_name(self, obj) -> str:
        return obj.product.name

    def get_product_slug(self, obj) -> str | None:
        return obj.product.slug

    def get_variant_label(self, obj) -> str | None:
        return obj.variant.option.label if obj.variant else None

    def get_sku(self, obj) -> str:
        return obj.variant.sku if obj.variant else obj.product.sku

    def get_image_url(self, obj) -> str | None:
        cover = (obj.product.images.filter(is_cover=True).first()
                 or obj.product.images.first())
        if not (cover and cover.image):
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(cover.image.url) if request else cover.image.url

    def get_subtotal(self, obj) -> str:
        return str((obj.price_unit * obj.product_uom_qty)
                   .quantize(Decimal('0.01')))

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
        return obj.current_price() != obj.price_unit


class DraftCartSerializer(serializers.ModelSerializer):
    """La ``SaleOrder(draft)`` presentada con el contrato histórico de
    ``CartSerializer``: 4 claves ``id``/``cart_token``/``items``/``totals``;
    ``totals`` delega en ``get_draft_totals`` (paridad de las 13 claves,
    verificada en TestDraftTotalsS2c).
    """
    items  = DraftItemSerializer(many=True, read_only=True,
                                 source='order_line')
    totals = serializers.SerializerMethodField()

    class Meta:
        model  = SaleOrder
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
