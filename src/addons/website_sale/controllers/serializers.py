"""Serializers — carrito del escaparate (``website_sale``).

El carrito **es** la ``SaleOrder`` en ``state='draft'``
(``odoo19c: addons/website_sale/models/sale_order.py:133`` la localiza
filtrando por ``Domain('state', '=', 'draft')``). Estos serializers no
declaran un modelo propio: proyectan esa orden y sus líneas al contrato que
el SPA ya consume.
"""
from rest_framework import serializers


class CartLineSerializer(serializers.Serializer):
    """Una línea del carrito — ≙ ``sale.order.line`` en la referencia."""

    id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(source='product_id', read_only=True)
    name = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(
        source='product_uom_qty', read_only=True)
    price_unit = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)


class AddCartItemSerializer(serializers.Serializer):
    """≙ ``/shop/cart/add`` (``odoo19c: controllers/cart.py:75``).

    La referencia recibe ``product_template_id`` **y** ``product_id`` porque
    su vitrina resuelve la variante en el cliente. Aquí el SPA manda la
    variante ya resuelta, así que sólo se recibe ``product_id`` — la
    plantilla se deriva de ella.
    """

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)


class UpdateCartItemSerializer(serializers.Serializer):
    """≙ ``/shop/cart/update`` (``odoo19c: controllers/cart.py:284``).

    Divergencia declarada: la referencia acepta ``quantity <= 0`` como
    *borrar la línea*. Aquí borrar tiene su propio verbo (``DELETE``), así
    que la cantidad es siempre ``>= 1`` — un PATCH que quiere decir "borra"
    es una ambigüedad que el REST no necesita.
    """

    quantity = serializers.IntegerField(min_value=1)


class ApplyVoucherSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)


class MergeCartSerializer(serializers.Serializer):
    """Fusión del carrito anónimo en el del usuario al iniciar sesión.

    Forma propia: la referencia no la necesita porque su carrito vive en la
    sesión y la sesión sobrevive al login. Aquí el carrito anónimo se ancla
    por ``cart_token`` (DEC-BC-07), así que la fusión es explícita.
    """

    cart_token = serializers.UUIDField()
