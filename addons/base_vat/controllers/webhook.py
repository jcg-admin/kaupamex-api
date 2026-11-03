"""El webhook de vuelta del VIES.

Adaptación de ``odoo19c: addons/base_vat/controllers/webhook.py``
(``odoo-tools@abe4040ec1``, LGPL-3, DEC-KX-03). La fuente declara
``@http.route('/base_vat/1/webhook_update_vies', type='http', csrf=False,
save_session=False, auth='public')``; aquí es una ``APIView`` con ``AllowAny`` y
``csrf_exempt``, el precedente de ``base_automation``: la autenticación es el
``webhook_token`` que :func:`_check_vies_iap` firmó con ``hash_sign`` en el
ámbito ``vies_check``, no una sesión.

``request.env(su=True)`` y ``with_user(SUPERUSER_ID)`` de la fuente son
``sudo()``. La ruta acepta ``GET`` y ``POST`` como el ``type='http'`` de la
fuente, que no restringe métodos.
"""

import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.base.models.res_partner import ResPartner
from orm.environments import env, sudo
from tools.misc import verify_hash_signed

_logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class BaseVatWebhookController(APIView):
    """≙ ``BaseVatWebhookController``."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['base_vat'],
        summary='Recibir del proxy IAP el estado VIES de un VAT',
        description=(
            'Llamado por IAP cuando un VAT sale del estado pendiente. El '
            'webhook_token lo firmó esta base al consultar; sin él no se toca '
            'ningún partner (≙ auth="public" de la referencia).'
        ),
        responses={200: OpenApiResponse(description='cuerpo vacío')},
    )
    def get(self, request):
        return self.webhook_update_vies(request)

    @extend_schema(exclude=True)
    def post(self, request):
        return self.webhook_update_vies(request)

    def webhook_update_vies(self, request):
        """El cuerpo, con el nombre de la fuente.

        Docstring de la fuente, verbatim: *"Webhook called by IAP when it
        updates a status from the pending state. The webhook_token is computed
        by the Odoo db (in _compute_vies_valid) and stored on IAP such that only
        IAP can call this webhook."*
        """
        params = request.query_params.copy()
        params.update(request.data)
        webhook_token = params.get('webhook_token', '')
        status = params.get('status')
        with sudo():
            try:
                vat = verify_hash_signed(env(), 'vies_check', webhook_token)
            except ValueError:
                vat = None
            if not vat:
                _logger.warning("VIES update failed: webhook_token does not match.")
                return Response(status=200)
            for partner in ResPartner.objects.filter(vat=vat):
                partner._update_vies_status(status)
        return Response(status=200)
