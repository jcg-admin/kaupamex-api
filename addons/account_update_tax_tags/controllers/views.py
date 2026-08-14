"""Vistas — ``addons.account_update_tax_tags``.

Acción única (recalcular y reescribir casillas fiscales) → FBV
``@api_view``, no ``ViewSet`` — criterio del skill ``backend-drf`` (tabla de
estilos Phase 7: "acción única" → FBV). Cierra H-API-406 para este wizard
(tarea #52) y realiza el contrato PROPUESTO de PARTE 7C de
``uc-fin-11-actualizar-casillas-fiscales``.

Capacidad: ``invoices`` — decisión ya tomada en ``security/__init__.py`` de
este addon ("opera sobre account.move.line ... que ya dueña account con la
capacidad invoices"). Se ratifica aquí, no se reabre (candidatos
alternos documentados en PARTE 9 del UC eran ``finance.close``/
``finance.record``; se prefiere la decisión ya escrita en código —
``referencia-odoo-gobierna-las-decisiones.md``: el puerto lleva la decisión
de la referencia, y aquí la decisión previa ya está en el propio repo).
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.account_update_tax_tags.controllers.serializers import (
    RecalculateTaxTagsResultSerializer,
    RecalculateTaxTagsSerializer,
)
from addons.account_update_tax_tags.wizard.account_update_tax_tags_wizard import (
    AccountUpdateTaxTagsWizard,
)
from addons.authz.permissions import require_capability
from exceptions import UserError


@extend_schema(
    tags=['finance'],
    summary='Recalcular casillas fiscales',
    request=RecalculateTaxTagsSerializer,
    responses={
        200: RecalculateTaxTagsResultSerializer,
        403: OpenApiResponse(description='Sin capacidad invoices, o '
                                          'REAUTH_REQUIRED (DEC-12)'),
        422: OpenApiResponse(description='TAX_TAGS_CHILD_TAX_SHARED — un '
                                          'impuesto hijo pertenece a más de '
                                          'un padre de la empresa'),
    },
)
@api_view(['POST'])
@require_capability('invoices')
def recalculate_tax_tags(request):
    """≙ ``AccountUpdateTaxTagsWizard.update_amls_tax_tags`` — UC-FIN-11.

    ``date_from`` cae al default de la referencia (día siguiente al
    candado fiscal) cuando el llamador no lo provee explícitamente.
    """
    serializer = RecalculateTaxTagsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    company = serializer.validated_data['company_id']
    date_from = (serializer.validated_data.get('date_from')
                 or AccountUpdateTaxTagsWizard.compute_date_from(company))

    try:
        impacted_ids = AccountUpdateTaxTagsWizard.update_amls_tax_tags(
            company, date_from)
    except UserError as exc:
        return Response(
            {'detail': str(exc), 'codigo_error': 'TAX_TAGS_CHILD_TAX_SHARED'},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    output = RecalculateTaxTagsResultSerializer({
        'date_from': date_from,
        'display_lock_date_warning':
            AccountUpdateTaxTagsWizard.display_lock_date_warning(company, date_from),
        'impacted_move_line_ids': impacted_ids,
    })
    return Response(output.data, status=status.HTTP_200_OK)
