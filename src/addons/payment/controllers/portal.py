"""``portal`` — lo que el comprador toca del pago.

Origen y correspondencia
========================

Adaptación de ``payment/controllers/portal.py`` (LGPL-3). Medido en las dos
poblaciones sobre ``odoo-tools@622ddc2a``: ``odoo19c`` y ``odoo18c`` declaran
el mismo archivo con las **mismas 6 rutas**, así que aquí no hay que
desempatar versión.

==============================  =========================================
Referencia (``portal.py``)      Aquí
==============================  =========================================
``/payment/transaction``        ``POST /api/v2/payments/initiate/``
``/payment/status``             ``GET  /api/v2/payments/<order_number>/status/``
``/my/payment_method``          ``GET  /api/v2/payments/<order_number>/history/``
``/payment/status/poll``        (no portada — ver abajo)
``/payment/confirmation``       (no portada — ver abajo)
``/payment/archive_token``      (no portada — ver abajo)
==============================  =========================================

Qué **no** se porta, y por qué
------------------------------

- ``/payment/status/poll`` — el *polling* del navegador mientras el proveedor
  resuelve. Aquí no hace falta: el gateway responde **síncrono**
  (``initiate_checkout_api_payment`` devuelve approved/rejected/pending en la
  misma llamada, ADR-018) y el webhook confirma después. Portar un poll sobre
  un canal síncrono sería infraestructura sin fenómeno que observar.
- ``/payment/confirmation`` — devuelve la página QWeb de "gracias por tu
  compra". Es render, y el render lo hace el SPA.
- ``/payment/archive_token`` — archivar una tarjeta guardada. El modelo
  (``SavedCard``) existe, pero su superficie es de cuenta, no de pago; se
  decidirá con el resto de ``/my/`` y no se inventa aquí.

Estilo y autorización
=====================

Las tres son de **un verbo sobre un recurso**, así que van como vistas
función (skill ``backend-drf``). Todas exigen sesión y van gateadas por
capacidad —``account.payments``, que ``base`` ya declara y siembra en todos
los roles (DEC-ENF-01)—: pagar y consultar pagos es cuenta propia. No se
inventa capacidad nueva (ver H-API-283).

La pertenencia se acota **por fila** antes que por capacidad: cada vista
filtra la orden por ``partner`` del solicitante, así que un ``order_number``
ajeno responde 404 y no confirma que exista.
"""
import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.payment.controllers.serializers import (
    InitiatePaymentSerializer,
    PaymentSerializer,
)
from addons.payment.models import Payment
from addons.payment.services import initiate_checkout_api_payment
from addons.sale.models import SaleOrder

_logger = logging.getLogger(__name__)


def _own_order(request, order_number):
    """La orden del solicitante, o ``None``.

    Acota por ``partner`` en el propio queryset: es la capa L3 (fila) y va
    antes que cualquier otra comprobación, para que una orden ajena sea
    indistinguible de una inexistente.
    """
    return (
        SaleOrder.objects
        .filter(name=order_number, partner__user=request.user)
        .first()
    )


@extend_schema(
    tags=['payments'],
    summary='Iniciar el pago de una orden',
    request=InitiatePaymentSerializer,
    responses={
        201: PaymentSerializer,
        404: OpenApiResponse(description='ORDER_NOT_FOUND'),
        409: OpenApiResponse(description='ORDER_NOT_PAYABLE'),
        502: OpenApiResponse(description='GATEWAY_ERROR'),
    },
)
@api_view(['POST'])
@require_capability('account.payments')
def initiate_payment(request):
    """≙ ``/payment/transaction``: crea la transacción con el proveedor.

    El servicio ya existía (``initiate_checkout_api_payment``); esto es sólo
    la capa HTTP que faltaba.
    """
    serializer = InitiatePaymentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    order = _own_order(request, data['order_number'])
    if order is None:
        return Response(
            {'codigo_error': 'ORDER_NOT_FOUND',
             'detail': 'La orden no existe.'},
            status=status.HTTP_404_NOT_FOUND)

    try:
        payment, _result = initiate_checkout_api_payment(
            order,
            token=data.get('token', ''),
            installments=data.get('installments', 1),
            payment_method_id=data.get('payment_method_id', ''),
            issuer_id=data.get('issuer_id', ''),
            payer_email=data.get('payer_email', ''),
        )
    except ValueError as exc:
        # La orden no está en un estado que admita cobro. Es conflicto de
        # estado, no dato inválido: el cuerpo de la petición estaba bien.
        return Response(
            {'codigo_error': 'ORDER_NOT_PAYABLE', 'detail': str(exc)},
            status=status.HTTP_409_CONFLICT)
    except RuntimeError as exc:
        # El proveedor falló. 502 y no 500: el error es de un tercero, y esa
        # distinción decide si el SPA reintenta o pide otro medio de pago.
        _logger.warning('Gateway error al iniciar pago de %s: %s',
                        order.name, exc)
        return Response(
            {'codigo_error': 'GATEWAY_ERROR',
             'detail': 'El proveedor de pagos no respondió.'},
            status=status.HTTP_502_BAD_GATEWAY)

    return Response(PaymentSerializer(payment).data,
                    status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['payments'],
    summary='Estado del pago de una orden',
    responses={
        200: PaymentSerializer,
        404: OpenApiResponse(description='ORDER_NOT_FOUND | NO_PAYMENT'),
    },
)
@api_view(['GET'])
@require_capability('account.payments')
def payment_status(request, order_number):
    """≙ ``/payment/status``: el último intento de cobro de la orden."""
    order = _own_order(request, order_number)
    if order is None:
        return Response(
            {'codigo_error': 'ORDER_NOT_FOUND',
             'detail': 'La orden no existe.'},
            status=status.HTTP_404_NOT_FOUND)

    payment = (
        Payment.objects.filter(sale_order=order).order_by('-created_at').first()
    )
    if payment is None:
        return Response(
            {'codigo_error': 'NO_PAYMENT',
             'detail': 'La orden todavía no tiene ningún intento de pago.'},
            status=status.HTTP_404_NOT_FOUND)
    return Response(PaymentSerializer(payment).data)


@extend_schema(
    tags=['payments'],
    summary='Historial de intentos de pago de una orden',
    responses={
        200: PaymentSerializer(many=True),
        404: OpenApiResponse(description='ORDER_NOT_FOUND'),
    },
)
@api_view(['GET'])
@require_capability('account.payments')
def payment_history(request, order_number):
    """Todos los intentos, no sólo el último.

    Forma propia: la referencia expone los **medios** guardados
    (``/my/payment_method``), no el historial por orden. Aquí importa porque
    un rechazo seguido de un aprobado deja dos filas, y el comprador tiene
    que poder ver por qué le rechazaron el primero.
    """
    order = _own_order(request, order_number)
    if order is None:
        return Response(
            {'codigo_error': 'ORDER_NOT_FOUND',
             'detail': 'La orden no existe.'},
            status=status.HTTP_404_NOT_FOUND)

    payments = Payment.objects.filter(sale_order=order).order_by('-created_at')
    return Response(PaymentSerializer(payments, many=True).data)
