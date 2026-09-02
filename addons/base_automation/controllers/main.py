"""``BaseAutomationController`` — addon ``base_automation``.

Adaptación de Odoo ``base_automation/controllers/main.py`` (LGPL-3): el
endpoint HTTP del webhook (Odoo ``/web/hook/<rule_uuid>``, ``auth='public'``,
sin CSRF). Mismo diseño que ``addons.delivery.webhooks`` /
``addons.payment.webhooks`` (ver su docstring): ``AllowAny`` +
``csrf_exempt`` — la autenticación es el propio ``webhook_uuid``
(no adivinable), igual que en la referencia.
"""
import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.base_automation.models.base_automation import (
    BaseAutomation,
    get_webhook_request_payload,
)

logger = logging.getLogger('apps')


@method_decorator(csrf_exempt, name='dispatch')
class BaseAutomationWebhookView(APIView):
    """≙ ``call_webhook_http`` de la referencia.

    ``GET``/``POST`` ``/web/hook/<rule_uuid>`` en la referencia; aquí el
    prefijo lo fija ``urls.py`` de este addon + ``config/urls.py`` (fuera
    de alcance de este pase, ver el reporte de retorno)."""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=['base_automation'],
        summary='Ejecutar el webhook de una regla de automatización',
        description=(
            'Localiza la regla por su webhook_uuid y ejecuta sus acciones '
            'sobre el registro que resuelva record_getter. La autenticación '
            'es el propio uuid — no adivinable, sin JWT (≙ Odoo auth="public").'
        ),
        responses={
            200: OpenApiResponse(description='{"status": "ok"}'),
            404: OpenApiResponse(description='{"status": "error"} — uuid no encontrado'),
            500: OpenApiResponse(description='{"status": "error"} — fallo al ejecutar'),
        },
    )
    def get(self, request, rule_uuid):
        return self.call_webhook_http(request, rule_uuid)

    @extend_schema(exclude=True)
    def post(self, request, rule_uuid):
        return self.call_webhook_http(request, rule_uuid)

    def call_webhook_http(self, request, rule_uuid):
        """El cuerpo, con el nombre de la fuente (``:7``).

        ``get``/``post`` son la puerta que DRF exige —el despacho por verbo es
        del mecanismo, no de la fuente, que declara los dos métodos en un solo
        ``@route(methods=['GET', 'POST'])``— y las dos delegan aquí. Conservar
        el nombre deja el símbolo de la referencia localizable por su nombre en
        vez de escondido tras un ``_call`` inventado.
        """
        rule = BaseAutomation.objects.filter(webhook_uuid=rule_uuid).first()
        if not rule:
            return Response({'status': 'error'}, status=404)
        payload = get_webhook_request_payload(request)
        try:
            rule._execute_webhook(payload)
        except Exception:  # noqa: BLE001 — ≙ "except Exception" de la referencia
            logger.warning(
                'base_automation webhook %s fallo', rule_uuid, exc_info=True)
            return Response({'status': 'error'}, status=500)
        return Response({'status': 'ok'}, status=200)
