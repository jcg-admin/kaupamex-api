"""``payment`` — el paso de pago del escaparate (checkout express).

Origen y correspondencia
========================

Adaptación de ``website_sale/controllers/payment.py``. Medido en las dos
poblaciones (``odoo-tools@622ddc2a``): ``odoo19c`` y ``odoo18c`` declaran el
mismo archivo con **una sola** ruta,
``/shop/payment/transaction/<int:order_id>``.

La ruta que aquí se porta no es ésa —esa es la transacción, y vive en
``payment/controllers/portal.py`` con el resto del cobro— sino el **checkout
express**: confirmar el carrito en un paso, sin recorrer las pantallas de
dirección y entrega.

===============================================  =========================
Referencia                                       Aquí
===============================================  =========================
``/shop/express/shipping_address_change``        (``delivery.py``, pendiente)
``/shop/payment`` + ``/shop/confirmation``       ``POST /api/v2/checkout/express/``
===============================================  =========================

**Por qué un solo endpoint y no tres.** La referencia reparte el checkout en
pantallas porque renderiza QWeb y cada paso es una página. El express de la
referencia existe justamente para saltárselas cuando el proveedor (Apple Pay,
Google Pay) ya trae dirección y método. Aquí el SPA está en esa misma
situación: manda todo junto y confirma. Portar tres endpoints para que el
cliente los llame en fila sería reproducir la forma de la página, no la del
flujo.

La confirmación la hace ``confirm_draft_order`` (``addons.sale.services``),
que ya existía: es la transición ``draft → sale`` que acuña el número de
orden. Este módulo es sólo la capa HTTP.
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.sale.services import (
    DraftOrderError,
    confirm_draft_order,
    get_or_create_draft_order,
)
from addons.website_sale.controllers.serializers import (
    ExpressCheckoutSerializer,
)


@extend_schema(
    tags=['checkout'],
    summary='Confirmar el carrito en un paso (checkout express)',
    request=ExpressCheckoutSerializer,
    responses={
        201: OpenApiResponse(description='order_number + total'),
        409: OpenApiResponse(description='EMPTY_CART | INSUFFICIENT_STOCK'),
    },
)
@api_view(['POST'])
@require_capability('account.orders')
def express_checkout(request):
    """Confirma el carrito del usuario con la dirección que trae el cuerpo.

    Un verbo, un recurso → vista función. Exige sesión y capacidad
    ``account.orders``: confirmar es crear una orden a nombre de alguien, y
    ese alguien tiene que estar identificado.
    """
    serializer = ExpressCheckoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    order, _created = get_or_create_draft_order(user=request.user)
    try:
        confirmed = confirm_draft_order(
            order,
            address_data=data['address'],
            notes=data.get('notes', ''),
        )
    except DraftOrderError as exc:
        return Response(
            {'codigo_error': exc.codigo_error, 'detail': str(exc)},
            status=status.HTTP_409_CONFLICT)

    return Response(
        {
            'order_number': confirmed.name,
            'total': str(confirmed.amount_total),
        },
        status=status.HTTP_201_CREATED,
    )
