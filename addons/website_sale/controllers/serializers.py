"""Serializers — carrito del escaparate (``website_sale``).

El carrito **es** la ``SaleOrder`` en ``state='draft'``
(``odoo19c: addons/website_sale/models/sale_order.py:133`` la localiza
filtrando por ``Domain('state', '=', 'draft')``). Estos serializers no
declaran un modelo propio: proyectan esa orden y sus líneas al contrato que
el SPA ya consume.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from addons.base.models.ir_http import IrHttp
from addons.product.models import ProductCategory, ProductTemplate


class ProductListSerializer(serializers.ModelSerializer):
    """Un producto en el listado del escaparate.

    Campos mínimos para pintar una tarjeta: lo que la ficha añade
    (descripción larga, atributos) no viaja en el listado — una vitrina de
    24 productos no necesita 24 descripciones completas.
    """

    slug = serializers.SerializerMethodField()
    category = serializers.CharField(source='categ.name', read_only=True,
                                     default=None)
    price = serializers.DecimalField(source='list_price', max_digits=12,
                                     decimal_places=2, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductTemplate
        fields = ['id', 'slug', 'name', 'default_code', 'category', 'price',
                  'image']

    @extend_schema_field(serializers.CharField())
    def get_slug(self, obj):
        """``_slug`` del producto — ``<nombre-slugificado>-<id>``.

        El id al final es lo que resuelve el registro; el texto es
        legibilidad y SEO.

        **Ya no se recompone aquí.** Este método construía
        ``f'{slugname}-{obj.pk}'`` a mano sobre ``IrHttp.slugify_one`` y
        declaraba su divergencia de SITIO con sucesor #261: en la referencia
        la composición vive en ``http_routing``, addon que este árbol no
        portaba. Ese addon existe desde #261, así que la composición se llama
        donde la fuente la declara — ``IrHttp._slug``
        (``odoo19c: addons/http_routing/models/ir_http.py:54-66``) — y este
        serializer vuelve a ser lo que era, un proyector.

        Lo que el cambio conserva, porque es la conducta que
        ``tests/unit/website_sale/test_the_product_slug_keeps_non_ascii.py``
        fija: el ``slugify`` es el portado y no el de Django (un producto
        llamado ``手工皂`` conserva su nombre en la URL, ver :ref:`h-api-993`),
        el nombre se lee de ``display_name``, y un nombre sin caracteres de
        palabra devuelve **sólo el id**, no ``-42``. Las tres las hace ahora
        ``_slug``, que es de donde salían.
        """
        return IrHttp._slug(obj)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image(self, obj):
        """La 512 — el tamaño que la referencia usa en la rejilla de ``/shop``.

        Se devuelve URL absoluta cuando hay ``request`` en el contexto; si no,
        relativa. Nunca revienta por falta de contexto.
        """
        image = getattr(obj, 'image_512', None)
        if not image:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(image.url) if request else image.url


class ProductDetailSerializer(ProductListSerializer):
    """La ficha completa — el listado más lo que sólo se lee al abrirla."""

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            'description_sale', 'weight', 'volume', 'is_published',
        ]


class CategoryTreeSerializer(serializers.ModelSerializer):
    """Una categoría con su descendencia anidada.

    ``children`` se resuelve recursivamente sobre ``child_id``, que es el
    ``related_name`` que este proyecto le dio al ``parent_id`` de la
    referencia.
    """

    children = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = ['id', 'name', 'complete_name', 'children']

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_children(self, obj):
        return CategoryTreeSerializer(
            obj.child_id.all().order_by('name'), many=True,
            context=self.context).data


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


class ExpressCheckoutSerializer(serializers.Serializer):
    """≙ el cuerpo del checkout express.

    La dirección viaja anidada y sin validación de campos aquí: quien la
    valida es ``confirm_draft_order``, que ya conoce las reglas de dirección
    del proyecto. Duplicar el esquema aquí crearía dos fuentes de verdad
    sobre qué es una dirección válida.

    ``shipping_method_id`` es opcional y su **coste** lo resuelve la vista
    consultando ``delivery`` — no se recibe el importe desde el cliente. Es
    el mismo orden de la referencia: ``_set_delivery_method`` fija el
    transportista y el precio sale de él, nunca del formulario.
    """

    address = serializers.DictField()
    shipping_method_id = serializers.IntegerField(required=False,
                                                  allow_null=True,
                                                  default=None)
    notes = serializers.CharField(max_length=500, required=False,
                                  allow_blank=True, default='')
