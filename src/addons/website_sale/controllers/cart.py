"""``cart`` — la superficie HTTP del carrito del escaparate.

Origen y correspondencia
========================

Adaptación de ``odoo19c: addons/website_sale/controllers/cart.py`` (LGPL-3,
leído completo) sobre ``odoo-tools@622ddc2a``. El archivo se llama igual que
su fuente: ``odoo19c`` parte el controlador en 11 módulos y ``cart.py`` es
uno de ellos, distinto de ``main.py`` (el escaparate y el checkout).

**El split es de 19, no de siempre.** Medido por población: ``odoo18c``
tiene 10 módulos y **no** tiene ``cart.py`` — sus cinco rutas de carrito
(``/shop/cart``, ``update``, ``update_json``, ``quantity``, ``clear``) viven
dentro de ``main.py`` (``odoo18c: website_sale/controllers/main.py:757-954``).
Se sigue a 19 porque 19 gobierna cuando las dos versiones difieren, y porque
su factorización es la que separa el carrito del checkout — que es
exactamente el corte que este porte necesita, con ``main.py`` aún sin portar.
No se sigue "porque la referencia lo hace así": una de las dos no lo hace.

El carrito **es** la ``SaleOrder`` en ``state='draft'``: la referencia lo
localiza filtrando por ``Domain('state', '=', 'draft')``
(``models/sale_order.py:133``) y sus rutas la materializan al añadir la
primera línea. Aquí es idéntico: no hay modelo de carrito, hay una orden en
borrador.

============================================  ==============================
Referencia (``controllers/cart.py``)          Aquí
============================================  ==============================
``GET  /shop/cart``           (``:20``)       ``GET    /api/v2/cart/``
``POST /shop/cart/add``       (``:75``)       ``POST   /api/v2/cart/items/``
``POST /shop/cart/update``    (``:284``)      ``PATCH  /api/v2/cart/items/<pk>/``
``POST /shop/cart/quantity``  (``:423``)      (en el cuerpo de ``GET /cart/``)
``POST /shop/cart/clear``     (``:435``)      ``DELETE /api/v2/cart/``
``POST /shop/cart/add`` (quick, ``:225``)     (mismo endpoint que ``add``)
============================================  ==============================

Toda la lógica ya estaba portada en ``addons.sale.services`` — este módulo es
**sólo la capa HTTP** que faltaba, que es exactamente lo que el mapa de porte
declara (``analisis-mapa-de-porte-website-sale``: *"CREAR la familia
—adaptar controllers sobre ``sale`` ya portado"*).

Estilo de vista (skill ``backend-drf``)
=======================================

No todo es ``APIView``; el estilo lo decide la forma del recurso:

- **Las líneas del carrito son un recurso CRUD** (colección + detalle) →
  ``CartItemViewSet`` con router. Es el caso que la guía manda modelar como
  ViewSet, y el router es obligatorio (un ``.as_view({...})`` manual se salta
  las ``permission_classes`` de la acción).
- **El carrito es un singleton**, no una colección: ``GET`` lo lee y
  ``DELETE`` lo vacía. Multi-método sin colección → ``APIView``. Igual el
  cupón, que es un sub-recurso de dos verbos.
- **Fusionar y guardar son acciones sueltas de un solo verbo** → vistas
  función (``@api_view``), sin la ceremonia de una clase por método.

Autorización
============

Las rutas del carrito son **públicas** (``AllowAny``) porque en la referencia
lo son (``auth='public'``): comprar sin cuenta es el caso normal del
escaparate.

El carrito **no se gatea por grupo**, y esto sí se sostiene en las dos
poblaciones que llevan el addon —``website_sale`` es Community, medido: 0
hits en ``odoo18e`` y ``odoo19e``—:

===========  ======================  =========================
Árbol        filas de la ACL         filas para ``sale.order``
===========  ======================  =========================
``odoo19c``  44                      **0**
``odoo18c``  60                      **0**
===========  ======================  =========================

La pertenencia se resuelve de la sesión y el controlador corre en ``sudo``.
Los tres ``res.groups`` propios de ``odoo19c`` son de *display*
(``group_show_uom_price``, ``group_product_price_comparison``,
``group_product_feed``) y los demás, de back-office (designer / sale manager).

**Este addon no declara capacidades propias.** Las dos superficies que sí
exigen sesión reusan las que ya dueña ``base`` —que en nuestra adaptación
hospeda la familia ``account.*`` y el menú de cuenta— porque cada una escribe
sobre un modelo que esa capacidad ya gobierna:

- ``merges`` → ``account.orders``: el carrito **es** la ``sale.order`` en
  borrador del comprador, el mismo modelo que esa capacidad gobierna.
- ``snapshots`` → ``account.wishlist``: escribe ``WishlistItem``, el modelo
  que el hermano ``website_sale_wishlist`` ya gatea con ella.

Inventar un ``account.cart`` habría añadido una capacidad que ni la
referencia declara ni ningún modelo nuevo justifica —y que además nadie
siembra, así que el gate fail-closed (DEC-11) respondería 403 a todo el
mundo. Lo que **no** se hace es caer en ``IsAuthenticated`` a secas: eso sí
saltaría el modelo de capacidades.

Divergencias declaradas
=======================

1. **Cómo se identifica el carrito anónimo.** La referencia lo guarda en la
   sesión (``CART_SESSION_CACHE_KEY = 'sale_order_id'``,
   ``models/website.py:24``) y no tiene ningún header propio — medido: 0
   apariciones de un token de carrito en todo el árbol. Aquí se ancla por
   ``SaleOrder.cart_token`` y viaja en el header ``X-Cart-Token``, que es
   **contrato ya decidido con el SPA** (DEC-BC-07) y campo ya portado en el
   modelo. El motivo es real, no de gusto: la referencia sirve QWeb desde el
   mismo origen que la sesión; aquí el escaparate es un SPA que puede
   consumir el API sin cookie de sesión previa.

2. **Borrar una línea tiene su propio verbo.** La referencia acepta
   ``quantity <= 0`` en ``/shop/cart/update`` como "borra la línea"
   (``:292-301``). En REST eso es ``DELETE``, y un ``PATCH`` que significa
   borrar es una ambigüedad que el contrato no necesita.

3. **Sin ``_render_template``.** ``update_cart`` de la referencia devuelve
   fragmentos QWeb ya renderizados (``:325-343``). Aquí la respuesta es el
   carrito serializado: el render lo hace el SPA.
"""
import logging

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import require_capability
from addons.product.models import ProductProduct
from addons.sale.services import (
    DraftOrderError,
    add_item_to_draft,
    clear_draft_items,
    get_draft_totals,
    get_or_create_draft_order,
    merge_draft_orders,
    remove_draft_item,
    update_draft_item_quantity,
)
from addons.sale_loyalty.services import (
    apply_voucher_to_draft,
    remove_voucher_from_draft,
)
from addons.website_sale.controllers.serializers import (
    AddCartItemSerializer,
    ApplyVoucherSerializer,
    MergeCartSerializer,
    UpdateCartItemSerializer,
)
from addons.website_sale_wishlist.models.wishlist import WishlistItem

_logger = logging.getLogger(__name__)

CART_TOKEN_HEADER = 'X-Cart-Token'


def _requested_cart_token(request):
    """El token del carrito anónimo que trae la petición, si lo trae."""
    return request.META.get('HTTP_X_CART_TOKEN') or None


def _resolve_cart(request):
    """≙ ``request.cart or request.website._create_cart()``.

    Autenticado → su único draft. Anónimo → el draft del token, creándolo si
    no existe. Es la misma bifurcación de la referencia, con el token en
    lugar de la sesión (ver divergencia 1 del módulo).
    """
    user = request.user if request.user.is_authenticated else None
    return get_or_create_draft_order(
        user=user, cart_token=_requested_cart_token(request))


def _cart_payload(order):
    """El carrito serializado: líneas + totales, el contrato que el SPA ya
    consume (``get_draft_totals`` sirve las 13 claves de siempre)."""
    return {
        'id': order.pk,
        'cart_token': str(order.cart_token) if order.cart_token else None,
        'items': [
            {
                'id': line.pk,
                'product_id': line.product_id,
                'name': line.name,
                'quantity': line.product_uom_qty,
                'price_unit': str(line.price_unit),
            }
            for line in order.order_line.select_related('product').all()
        ],
        'totals': get_draft_totals(order),
    }


def _with_cart_token(response, order):
    """Propaga el token al SPA. Sólo el carrito anónimo lo lleva — el de un
    usuario autenticado se resuelve por su partner y no necesita token."""
    if order.cart_token:
        response[CART_TOKEN_HEADER] = str(order.cart_token)
    return response


def _draft_error(exc):
    """409 — el carrito está en un estado que impide la operación (stock que
    ya no alcanza, línea que otro dispositivo borró)."""
    return Response(
        {'codigo_error': exc.codigo_error, 'detail': str(exc)},
        status=status.HTTP_409_CONFLICT,
    )


def _voucher_error(exc):
    """400 salvo el conflicto real de estado.

    Un cupón inexistente, vencido, agotado o que no alcanza el mínimo es un
    **dato inválido en la petición** (400): el carrito está bien, lo que
    está mal es el código que se mandó. ``VOUCHER_ALREADY_APPLIED`` sí es
    conflicto de estado (409) — el carrito ya tiene uno y hay que quitarlo
    primero (DEC-BC-20).
    """
    if exc.codigo_error == 'VOUCHER_ALREADY_APPLIED':
        return _draft_error(exc)
    return Response(
        {'codigo_error': exc.codigo_error, 'detail': str(exc)},
        status=status.HTTP_400_BAD_REQUEST,
    )


class CartView(APIView):
    """≙ ``/shop/cart`` (``odoo19c: controllers/cart.py:20``) y
    ``/shop/cart/clear`` (``:435``).

    Singleton, no colección: por eso ``APIView`` y no ViewSet.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['cart'],
        summary='Ver el carrito activo',
        responses={200: OpenApiResponse(description='líneas + totales')},
        auth=[],
    )
    def get(self, request):
        order, _created = _resolve_cart(request)
        return _with_cart_token(Response(_cart_payload(order)), order)

    @extend_schema(
        tags=['cart'],
        summary='Vaciar el carrito',
        responses={200: OpenApiResponse(description='carrito vacío')},
        auth=[],
    )
    def delete(self, request):
        """≙ ``clear_cart`` (``:441``): borra las líneas, no la orden. El
        carrito sigue existiendo vacío, igual que en la referencia."""
        order, _created = _resolve_cart(request)
        clear_draft_items(order)
        order.refresh_from_db()
        return _with_cart_token(Response(_cart_payload(order)), order)


class CartItemViewSet(viewsets.ViewSet):
    """Las líneas del carrito — ≙ ``/shop/cart/add`` (``:75``) y
    ``/shop/cart/update`` (``:284``).

    Es un recurso CRUD (colección ``items/`` + detalle ``items/<pk>/``), así
    que va como ViewSet cableado por router. ``ViewSet`` pelado y no
    ``ModelViewSet`` porque las líneas no se sirven por queryset propio: se
    crean, actualizan y borran **a través de los servicios de ``sale``**, que
    son los que aplican stock, precio y recálculo de totales. Un
    ``ModelViewSet`` invitaría a escribir la línea directamente y saltarse
    esa lógica.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['cart'],
        summary='Añadir un producto al carrito',
        request=AddCartItemSerializer,
        responses={
            201: OpenApiResponse(description='carrito con la línea añadida'),
            404: OpenApiResponse(description='PRODUCT_NOT_FOUND'),
            409: OpenApiResponse(description='INSUFFICIENT_STOCK | '
                                             'PRODUCT_UNAVAILABLE'),
        },
        auth=[],
    )
    def create(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        product = ProductProduct.objects.filter(pk=data['product_id']).first()
        if product is None:
            return Response(
                {'codigo_error': 'PRODUCT_NOT_FOUND',
                 'detail': 'El producto no existe.'},
                status=status.HTTP_404_NOT_FOUND)

        order, _created = _resolve_cart(request)
        try:
            add_item_to_draft(order, product, quantity=data['quantity'])
        except DraftOrderError as exc:
            return _draft_error(exc)

        order.refresh_from_db()
        return _with_cart_token(
            Response(_cart_payload(order), status=status.HTTP_201_CREATED),
            order)

    @extend_schema(
        tags=['cart'],
        summary='Cambiar la cantidad de una línea',
        request=UpdateCartItemSerializer,
        responses={
            200: OpenApiResponse(description='carrito actualizado'),
            409: OpenApiResponse(description='ITEM_NOT_FOUND | '
                                             'INSUFFICIENT_STOCK'),
        },
        auth=[],
    )
    def partial_update(self, request, pk=None):
        serializer = UpdateCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, _created = _resolve_cart(request)
        try:
            update_draft_item_quantity(
                order, pk, serializer.validated_data['quantity'])
        except DraftOrderError as exc:
            return _draft_error(exc)
        order.refresh_from_db()
        return _with_cart_token(Response(_cart_payload(order)), order)

    @extend_schema(
        tags=['cart'],
        summary='Quitar una línea del carrito',
        responses={
            200: OpenApiResponse(description='carrito actualizado'),
            409: OpenApiResponse(description='ITEM_NOT_FOUND'),
        },
        auth=[],
    )
    def destroy(self, request, pk=None):
        order, _created = _resolve_cart(request)
        try:
            remove_draft_item(order, pk)
        except DraftOrderError as exc:
            return _draft_error(exc)
        order.refresh_from_db()
        return _with_cart_token(Response(_cart_payload(order)), order)


class CartVoucherView(APIView):
    """Aplicar y quitar el cupón del carrito.

    Sub-recurso de dos verbos sobre el carrito singleton — no es una
    colección, así que ``APIView`` (mismo criterio que ``CartView``).

    En la referencia el cupón entra por ``website_sale_loyalty``, un addon
    puente aparte; aquí ``sale_loyalty`` ya trae los servicios
    (``apply_voucher_to_draft`` / ``remove_voucher_from_draft``) y sólo
    faltaba exponerlos.

    **Un cupón a la vez (DEC-BC-20).** Aplicar un segundo con uno ya activo
    no lo reemplaza en silencio: responde ``409 VOUCHER_ALREADY_APPLIED`` y
    obliga al flujo explícito ``DELETE`` + ``POST``. Reemplazar callado
    escondería del comprador cuál de los dos descuentos quedó.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['cart'],
        summary='Aplicar un cupón al carrito',
        request=ApplyVoucherSerializer,
        responses={
            200: OpenApiResponse(description='descuento aplicado'),
            400: OpenApiResponse(description='VOUCHER_NOT_FOUND | '
                                             'VOUCHER_EXPIRED | '
                                             'VOUCHER_EXHAUSTED | '
                                             'MIN_ORDER_NOT_MET'),
            409: OpenApiResponse(description='VOUCHER_ALREADY_APPLIED'),
        },
        auth=[],
    )
    def post(self, request):
        serializer = ApplyVoucherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, _created = _resolve_cart(request)
        user = request.user if request.user.is_authenticated else None
        try:
            voucher, discount, cart_total = apply_voucher_to_draft(
                order, serializer.validated_data['code'], user=user)
        except DraftOrderError as exc:
            return _voucher_error(exc)
        order.refresh_from_db()
        payload = _cart_payload(order)
        payload['voucher'] = {
            'code': voucher.code,
            'discount': str(discount),
            'cart_total': str(cart_total),
        }
        return _with_cart_token(Response(payload), order)

    @extend_schema(
        tags=['cart'],
        summary='Quitar el cupón del carrito',
        responses={
            200: OpenApiResponse(description='carrito sin descuento'),
            400: OpenApiResponse(description='NO_ACTIVE_VOUCHER'),
        },
        auth=[],
    )
    def delete(self, request):
        order, _created = _resolve_cart(request)
        try:
            remove_voucher_from_draft(order)
        except DraftOrderError as exc:
            return _voucher_error(exc)
        order.refresh_from_db()
        return _with_cart_token(Response(_cart_payload(order)), order)


@extend_schema(
    tags=['cart'],
    summary='Fusionar el carrito anónimo en el del usuario',
    request=MergeCartSerializer,
    responses={200: OpenApiResponse(description='carrito fusionado')},
)
@api_view(['POST'])
@require_capability('account.orders')
def merge_cart(request):
    """Fusionar el carrito anónimo en el del usuario al iniciar sesión.

    Forma propia declarada: la referencia no la necesita porque su carrito
    vive en la sesión, y la sesión sobrevive al login. Aquí el anónimo se
    ancla por ``cart_token`` (DEC-BC-07), así que la fusión es un paso
    explícito. Un solo verbo → vista función.
    """
    serializer = MergeCartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # El servicio devuelve también las líneas que NO pudieron migrar (sin
    # stock al momento de fusionar). Se reportan: perderlas en silencio
    # dejaría al comprador creyendo que su carrito viajó entero.
    order, skipped = merge_draft_orders(
        request.user, serializer.validated_data['cart_token'])
    payload = _cart_payload(order)
    payload['skipped'] = skipped
    return Response(payload)


@extend_schema(
    tags=['cart'],
    summary='Guardar el carrito en la lista de deseos',
    request=None,
    responses={
        200: OpenApiResponse(description='saved_count + detail'),
        400: OpenApiResponse(description='EMPTY_CART'),
    },
)
@api_view(['POST'])
@require_capability('account.wishlist')
def save_cart_for_later(request):
    """Guardar el carrito para después — mover sus líneas a la lista de deseos.

    **Forma propia declarada.** La referencia no la tiene: sus cuatro rutas de
    ``website_sale_wishlist`` (``odoo19c: controllers/main.py:8,35,46,59``)
    van del catálogo a la lista, nunca del carrito. Es la composición inversa
    de ``cart-transfers``, que el hermano ya declara como forma propia por el
    mismo motivo — allá el botón mueve un deseo al carrito, aquí mueve el
    carrito a los deseos.

    Gateada por ``account.wishlist`` —la misma que el hermano— porque lo que
    escribe es ``WishlistItem``: la lista cuelga del usuario, así que un
    carrito anónimo no tiene dónde guardarse.
    """
    order, _created = _resolve_cart(request)
    lines = list(order.order_line.select_related('product').all())
    if not lines:
        return Response(
            {'codigo_error': 'EMPTY_CART',
             'detail': 'No hay nada que guardar: el carrito está vacío.'},
            status=status.HTTP_400_BAD_REQUEST)

    saved = 0
    with transaction.atomic():
        for line in lines:
            # ``get_or_create`` en vez de ``create``: el producto puede estar
            # ya en la lista y el UNIQUE(user, product) lo rechazaría.
            # Guardar dos veces no es un error del comprador.
            _item, created = WishlistItem.objects.get_or_create(
                user=request.user, product=line.product,
                defaults={'price_at_add': line.price_unit},
            )
            if created:
                saved += 1
        clear_draft_items(order)

    order.refresh_from_db()
    return Response({
        'saved_count': saved,
        'detail': f'{saved} producto(s) guardado(s) en tu lista de deseos.',
        'cart': _cart_payload(order),
    })
