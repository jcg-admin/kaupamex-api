"""Vistas — ``addons.account_check_printing``.

Acción única (numerar/postear/marcar como enviado un lote de cheques) → FBV
``@api_view``, no ``ViewSet`` — criterio del skill ``backend-drf`` (tabla de
estilos Phase 7: "acción única (1 verbo)" → FBV). Cierra H-API-406 para este
wizard (tarea #50) y realiza el contrato PROPUESTO de PARTE 7C de
``uc-fin-09-imprimir-cheques-prenumerados``.

Capacidad: ``finance.record`` — decisión ya tomada en
``security/__init__.py`` de este addon ("el enforcement queda DEFERIDO a la
vista que en el futuro exponga ... gateada por HasCapability('finance.record')").
Se ratifica aquí, no se reabre (candidato alterno documentado en PARTE 9 del
UC era ``finance.disburse``; se prefiere la decisión ya escrita en código —
``referencia-odoo-gobierna-las-decisiones.md``: el puerto lleva la decisión).

Divergencia declarada — el caso exitoso no llega al render (H-API-407, #280)
====================================================================================

``print_checks`` del wizard SIEMPRE termina llamando ``render_checks``, que
alza ``NotImplementedError`` (``account_check_printing`` no declara todavía
su ``ReportSpec`` contra el motor de reportes ya existente — ``base.
report_catalog`` + ``tools/pdf``, ADR-017; ver H-API-407). Esta vista NO
inventa un render — expone el estado real: captura ``NotImplementedError``
y responde 500 con ``codigo_error='CHECK_PRINTING_REPORT_ENGINE_PENDING'``,
confirmando en el cuerpo los efectos que SÍ ocurrieron antes de ese punto
(posteo, numeración, marca de enviado — todos side effects reales, ya
persistidos). Cerrar el ``ReportSpec`` es la tarea #280, fuera de esta.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.account_check_printing.controllers.serializers import (
    PrintPrenumberedChecksSerializer,
)
from addons.account_check_printing.models.account_payment import (
    CheckPrintingPaymentInfo,
)
from addons.account_check_printing.wizard.print_prenumbered_checks import (
    PrintPrenumberedChecksWizard,
)
from addons.authz.permissions import require_capability
from exceptions import UserError


@extend_schema(
    tags=['finance'],
    summary='Imprimir cheques prenumerados',
    request=PrintPrenumberedChecksSerializer,
    responses={
        400: OpenApiResponse(description='CHECK_NUMBER_NOT_NUMERIC — el número '
                                          'inicial no es sólo dígitos'),
        403: OpenApiResponse(description='Sin capacidad finance.record, o '
                                          'REAUTH_REQUIRED (DEC-12)'),
        409: OpenApiResponse(description='CHECK_NUMBER_DUPLICATE — colisión de '
                                          'numeración dentro del diario'),
        422: OpenApiResponse(description='CHECK_LAYOUT_NOT_CONFIGURED — el '
                                          'diario no tiene diseño de cheque'),
        500: OpenApiResponse(description='CHECK_PRINTING_REPORT_ENGINE_PENDING '
                                          '— ver H-API-407 / tarea #280; los '
                                          'pagos SÍ quedan numerados y enviados'),
    },
)
@api_view(['POST'])
@require_capability('finance.record')
def print_checks(request):
    """≙ ``PrintPrenumberedChecksWizard.print_checks`` — UC-FIN-09.

    Numera secuencialmente el lote, postea los pagos en borrador, valida
    unicidad del número por diario y marca como enviados — ver el docstring
    del módulo para la divergencia declarada del paso final (render).
    """
    serializer = PrintPrenumberedChecksSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payments = serializer.validated_data['payment_ids']
    next_check_number = serializer.validated_data['next_check_number']

    try:
        PrintPrenumberedChecksWizard.print_checks(payments, next_check_number)
    except DjangoValidationError as exc:
        detail = '; '.join(exc.messages)
        duplicate = 'already used' in detail
        return Response(
            {'detail': detail,
             'codigo_error': 'CHECK_NUMBER_DUPLICATE' if duplicate
                              else 'CHECK_NUMBER_NOT_NUMERIC'},
            status=status.HTTP_409_CONFLICT if duplicate
                   else status.HTTP_400_BAD_REQUEST,
        )
    except UserError as exc:
        return Response(
            {'detail': str(exc), 'codigo_error': 'CHECK_LAYOUT_NOT_CONFIGURED'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except NotImplementedError as exc:
        rows = {
            row.payment_id: row for row in
            CheckPrintingPaymentInfo.objects.filter(
                payment_id__in=[p.pk for p in payments])
        }
        return Response(
            {
                'detail': str(exc),
                'codigo_error': 'CHECK_PRINTING_REPORT_ENGINE_PENDING',
                'payments': [
                    {
                        'payment_id': p.pk,
                        'check_number': rows[p.pk].check_number if p.pk in rows else '',
                        'state': p.state,
                    }
                    for p in payments
                ],
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
