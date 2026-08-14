"""Vistas — ``addons.account`` (registro de pago, UC-PAY-14).

Acción sobre un recurso con ``pk`` → FBV ``@api_view`` (criterio del skill
``backend-drf``: acción única sobre un detail no justifica un ``ViewSet``
completo cuando no hay list/retrieve/update/destroy que exponer — mismo
patrón que ``payment/controllers/portal.py::payment_status``). Cierra
H-API-408 / UC-PAY-14 (tarea #55): ``payment_state`` portado
(``account_move.py``) + la acción de registro que la referencia declara en
``odoo19c: addons/account/wizard/account_payment_register.py``.

Capacidad: ``finance.record`` — "Registrar movimiento/concepto financiero"
(``authz_catalog.py``, ya declarada; no se inventa una nueva ni se usa el
candidato alterno que PARTE 9 del UC dejó abierto —
``referencia-odoo-gobierna-las-decisiones.md``: se prefiere la decisión ya
escrita en código, mismo criterio que ratificó H-API-406 para
``print_checks``, cuya naturaleza de acción —crear el apunte de un
movimiento financiero— es la misma que ésta).
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.account.controllers.serializers import (
    RegisterPaymentResultSerializer,
    RegisterPaymentSerializer,
)
from addons.account.models import AccountMove
from addons.account.wizard.account_payment_register import AccountPaymentRegisterWizard
from addons.authz.permissions import require_capability
from exceptions import UserError

#: ≙ las condiciones de PARTE 5 / PRE-01 / PRE-03 del UC, en el orden en que
#: ``AccountPaymentRegisterWizard.register_payment`` las evalúa — el primer
#: fragmento que aparece en el mensaje decide el ``codigo_error``.
_ERROR_CODES = (
    ('no está publicado', 'INVOICE_NOT_POSTED',
     status.HTTP_422_UNPROCESSABLE_ENTITY),
    ('no tiene línea por cobrar', 'INVOICE_NO_RECEIVABLE_LINE',
     status.HTTP_422_UNPROCESSABLE_ENTITY),
    ('diario no tiene cuenta', 'JOURNAL_ACCOUNT_MISSING',
     status.HTTP_422_UNPROCESSABLE_ENTITY),
    ('excede el saldo pendiente', 'AMOUNT_EXCEEDS_RESIDUAL',
     status.HTTP_409_CONFLICT),
    ('monto debe ser mayor a cero', 'AMOUNT_NOT_POSITIVE',
     status.HTTP_400_BAD_REQUEST),
    ('cuenta de diferencia', 'DIFFERENCE_ACCOUNT_REQUIRED',
     status.HTTP_400_BAD_REQUEST),
)
_DEFAULT_ERROR = ('INVOICE_REGISTER_PAYMENT_FAILED',
                   status.HTTP_422_UNPROCESSABLE_ENTITY)


def _error_response(exc):
    detail = str(exc)
    for needle, codigo, http_status in _ERROR_CODES:
        if needle in detail:
            return Response({'detail': detail, 'codigo_error': codigo},
                             status=http_status)
    codigo, http_status = _DEFAULT_ERROR
    return Response({'detail': detail, 'codigo_error': codigo}, status=http_status)


@extend_schema(
    tags=['finance'],
    summary='Registrar un pago (abono o pago completo) sobre una factura',
    request=RegisterPaymentSerializer,
    responses={
        201: RegisterPaymentResultSerializer,
        400: OpenApiResponse(description='AMOUNT_NOT_POSITIVE / '
                                          'DIFFERENCE_ACCOUNT_REQUIRED'),
        403: OpenApiResponse(description='Sin capacidad finance.record, o '
                                          'REAUTH_REQUIRED (DEC-12)'),
        404: OpenApiResponse(description='INVOICE_NOT_FOUND'),
        409: OpenApiResponse(description='AMOUNT_EXCEEDS_RESIDUAL'),
        422: OpenApiResponse(description='INVOICE_NOT_POSTED / '
                                          'INVOICE_NO_RECEIVABLE_LINE / '
                                          'JOURNAL_ACCOUNT_MISSING'),
    },
)
@api_view(['POST'])
@require_capability('finance.record')
def register_payment(request, pk):
    """≙ el botón "Registrar Pago" de ``account.payment.register`` — UC-PAY-14
    (:ref:`uc-pay-14-pago-parcial-abono`).

    Consume el álgebra de conciliación ya portada
    (``AccountPartialReconcile``/``AccountFullReconcile``, :ref:`h-api-408`);
    ver el docstring de ``AccountPaymentRegisterWizard.register_payment``
    para la mecánica completa (AC-01/AC-02/AC-03).
    """
    try:
        move = AccountMove.objects.get(pk=pk)
    except AccountMove.DoesNotExist:
        return Response(
            {'detail': 'La factura/asiento no existe.',
             'codigo_error': 'INVOICE_NOT_FOUND'},
            status=status.HTTP_404_NOT_FOUND)

    serializer = RegisterPaymentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        payment_move, partials = AccountPaymentRegisterWizard.register_payment(
            move,
            amount=data['amount'],
            journal=data['journal_id'],
            difference_handling=data.get('difference_handling', 'open'),
            difference_account=data.get('difference_account_id'),
            difference_label=data.get('difference_label') or 'Write-Off',
            date=data.get('date'),
        )
    except UserError as exc:
        return _error_response(exc)

    output = RegisterPaymentResultSerializer({
        'invoice_id': move.pk,
        'payment_move_id': payment_move.pk,
        'payment_state': move.payment_state,
        'amount_residual': move.get_amount_residual(),
        'partial_reconcile_ids': [p.pk for p in partials],
    })
    return Response(output.data, status=status.HTTP_201_CREATED)
