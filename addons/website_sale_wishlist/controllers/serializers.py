"""Serializers — ``website_sale_wishlist`` (UC-WISH-01/02/03).

Adaptación del contrato de lectura del ``product.wishlist`` de la
referencia (``odoo19c: website_sale_wishlist``, LGPL-3) al catálogo
plantilla/variante actual:

- el ``product`` anidado es la **variante** (``product.ProductProduct``),
  igual que el ``product_id`` de la referencia;
- ``slug`` NO es columna: en la referencia el slug se computa al armar la
  URL (``ir.http._slugify``) — aquí se computa igual, con el ``slugify``
  ya portado en ``base.models.ir_http``;
- ``base_price``/``current_price`` leen ``lst_price`` (precio de ficha +
  extra de atributos), la propiedad computada de la variante;
- ``stock``/``availability`` se DERIVAN de ``stock.quant`` vía
  ``InventoryService`` (odoo19c: ``stock/models/stock_quant.py:119-122``),
  no de una columna del producto.

Los campos planos (``product_name``/``image_url``/…) son el contrato que
``WishlistPage.jsx`` consume (H-CICLO37-03). ``image_url`` y
``orisha_name`` devuelven ``None``: el catálogo actual no porta imágenes
de e-commerce (viven en ``website_sale`` en la referencia — llegarán con
esa familia) ni un eje orisha.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers as drf_serializers
from rest_framework.serializers import ModelSerializer, SerializerMethodField

from addons.base.models.ir_http import IrHttp
from addons.stock.services import InventoryService
from addons.website_sale_wishlist.models import WishlistItem


class WishlistProductNestedSerializer(drf_serializers.Serializer):
    """Ficha compacta de la variante anidada en el item."""

    id = drf_serializers.IntegerField(read_only=True)
    name = drf_serializers.CharField(read_only=True)
    slug = SerializerMethodField()
    base_price = SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_slug(self, obj):
        return IrHttp.slugify_one(obj.name)

    @extend_schema_field(OpenApiTypes.STR)
    def get_base_price(self, obj):
        return str(obj.lst_price)


class WishlistItemSerializer(ModelSerializer):

    product = WishlistProductNestedSerializer(read_only=True)
    current_price = SerializerMethodField()
    price_dropped = SerializerMethodField()
    price_drop_percent = SerializerMethodField()
    availability = SerializerMethodField()
    # Aliases planos requeridos por WishlistPage.jsx (H-CICLO37-03).
    product_name = SerializerMethodField()
    image_url = SerializerMethodField()
    category_name = SerializerMethodField()
    orisha_name = SerializerMethodField()
    is_available = SerializerMethodField()
    stock = SerializerMethodField()

    class Meta:
        model = WishlistItem
        fields = [
            'id', 'product',
            'price_at_add', 'current_price',
            'price_dropped', 'price_drop_percent',
            'availability', 'created_at',
            'product_name', 'image_url', 'category_name',
            'orisha_name', 'is_available', 'stock',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_current_price(self, obj):
        return str(obj.current_price)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_price_dropped(self, obj):
        return obj.current_price < obj.price_at_add

    @extend_schema_field(OpenApiTypes.INT)
    def get_price_drop_percent(self, obj):
        if obj.price_at_add and obj.current_price < obj.price_at_add:
            pct = (1 - obj.current_price / obj.price_at_add) * 100
            return round(float(pct))
        return 0

    @extend_schema_field(OpenApiTypes.STR)
    def get_availability(self, obj):
        return 'IN_STOCK' if obj.is_available else 'OUT_OF_STOCK'

    @extend_schema_field(OpenApiTypes.STR)
    def get_product_name(self, obj):
        return obj.product.name

    @extend_schema_field(OpenApiTypes.STR)
    def get_image_url(self, obj):
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_category_name(self, obj):
        categ = obj.product.categ
        return categ.name if categ else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_orisha_name(self, obj):
        return None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_available(self, obj):
        return obj.is_available

    @extend_schema_field(OpenApiTypes.INT)
    def get_stock(self, obj):
        return int(InventoryService.available_quantity(obj.product))
