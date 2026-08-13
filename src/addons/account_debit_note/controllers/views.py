"""Vistas — ``addons.account_debit_note``.

Acción única (crear una o más notas de débito) → FBV ``@api_view``, no
``ViewSet`` — criterio del skill ``backend-drf`` (tabla de estilos Phase 7:
"acción única" → FBV). Cierra H-API-406 para este wizard (tarea #51) y
realiza el contrato PROPUESTO de PARTE 7C de
``uc-fin-10-crear-nota-de-debito``.

Capacidad: ``invoices`` — decisión ya tomada en ``security/__init__.py`` de
este addon ("la nota de débito es una operación sobre account.move, que ya
dueña account con la capacidad invoices"). Se ratifica aquí, no se reabre
(candidato alterno documentado en PARTE 9 del UC era ``finance.record``; se
prefiere la decisión ya escrita en código —
``referencia-odoo-gobierna-las-decisiones.md``: el puerto lleva la decisión
de la referencia, y aquí la decisión previa ya está en el propio repo).
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.account_debit_note.controllers.serializers import (
    CreateDebitNoteSerializer,
    DebitNoteResultSerializer,
)
from addons.account_debit_note.wizard.account_debit_note import AccountDebitNoteWizard
from addons.authz.permissions import require_capability
from exceptions import UserError

#: ≙ las tres condiciones de ``validate_moves`` (``account_debit_note.py``),
#: en el mismo orden en que el wizard las evalúa — el primer fragmento que
#: aparece en el mensaje decide el ``codigo_error``. "vinculada" primero:
#: su mensaje también contiene "nota de débito", que no debe capturar la
#: rama de tipo inválido.
_ERROR_CODES = (
    ('vinculada a otra nota', 'DEBIT_NOTE_ALREADY_LINKED',
     status.HTTP_409_CONFLICT),
    ('publicados', 'DEBIT_NOTE_MOVE_NOT_POSTED',
     status.HTTP_422_UNPROCESSABLE_ENTITY),
)
_DEFAULT_ERROR = ('DEBIT_NOTE_INVALID_MOVE_TYPE',
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
    summary='Crear nota de débito',
    request=CreateDebitNoteSerializer,
    responses={
        201: DebitNoteResultSerializer(many=True),
        403: OpenApiResponse(description='Sin capacidad invoices, o '
                                          'REAUTH_REQUIRED (DEC-12)'),
        409: OpenApiResponse(description='DEBIT_NOTE_ALREADY_LINKED'),
        422: OpenApiResponse(description='DEBIT_NOTE_MOVE_NOT_POSTED / '
                                          'DEBIT_NOTE_INVALID_MOVE_TYPE'),
    },
)
@api_view(['POST'])
@require_capability('invoices')
def create_debit_note(request):
    """≙ ``AccountDebitNoteWizard.create_debit`` — UC-FIN-10.

    Valida elegibilidad de cada movimiento de origen, prepara los valores
    del nuevo movimiento (con conversión de tipo para refunds) y crea una
    nota de débito ``draft`` por movimiento, opcionalmente copiando líneas.
    """
    serializer = CreateDebitNoteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        new_moves = AccountDebitNoteWizard.create_debit(
            data['move_ids'],
            date=data.get('date'),
            reason=data.get('reason'),
            journal=data.get('journal_id'),
            copy_lines=data.get('copy_lines', False),
        )
    except UserError as exc:
        return _error_response(exc)

    output = DebitNoteResultSerializer(new_moves, many=True)
    return Response(output.data, status=status.HTTP_201_CREATED)
