"""``referral`` — el programa de referidos del comprador.

**Superávit local declarado.** El análisis de la familia
(``analisis-familia-loyalty.rst:158-159``) ya lo midió: *"``referral`` no
existe como módulo Odoo en esta familia; el proyecto lo resuelve con
``Voucher`` tipo REFERRAL"*, y lo clasifica como *"superávit local sin
contraparte Odoo"* (``:383``). Así que aquí no hay puerto que seguir: hay una
forma propia, y se dice.

Lo que **sí** viene de la referencia es el sustrato: cada código se respalda
como un ``Voucher`` de tipo ``REFERRAL`` para reutilizar su validación de
vigencia y de uso, en vez de duplicar esas reglas. Por eso el hogar del
programa es ``loyalty`` y no un addon propio — es la capa de referidos del
framework de fidelidad, no un dominio aparte.

Autorización: ``account.referral``, que ``base`` ya declara
(``authz_catalog.py:53``) y siembra en el rol Comprador por su prefijo
``account.``. No se inventa capacidad (ver H-API-283).

Estilo: dos acciones de un verbo → vistas función (skill ``backend-drf``).
"""
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.loyalty.controllers.serializers import (
    RedeemReferralSerializer,
    ReferralProgramSerializer,
)
from addons.loyalty.models import Referral, ReferralCode


@extend_schema(
    tags=['referral'],
    summary='Mi programa de referidos',
    responses={200: ReferralProgramSerializer},
)
@api_view(['GET'])
@require_capability('account.referral')
def referral_program(request):
    """Mi código y a quién he referido.

    El código se genera al primer acceso: ``get_or_create_for_user`` es
    idempotente, así que consultar el programa no tiene efecto observable
    más allá de materializar lo que ya era del usuario.
    """
    code = ReferralCode.get_or_create_for_user(request.user)
    referrals = Referral.objects.filter(referrer=request.user)
    return Response(ReferralProgramSerializer({
        'code': code.code,
        'total': referrals.count(),
        'completed': referrals.filter(
            status=Referral.STATUS_COMPLETED).count(),
    }).data)


@extend_schema(
    tags=['referral'],
    summary='Canjear un código de referido',
    request=RedeemReferralSerializer,
    responses={
        201: OpenApiResponse(description='Referido registrado'),
        404: OpenApiResponse(description='REFERRAL_CODE_NOT_FOUND'),
        409: OpenApiResponse(description='SELF_REFERRAL | '
                                         'ALREADY_REFERRED'),
    },
)
@api_view(['POST'])
@require_capability('account.referral')
def redeem_referral(request):
    """Canjear el código de otro comprador.

    Tres rechazos, y los tres son de estado, no de dato — por eso 409 y no
    400 salvo el código inexistente:

    - **``SELF_REFERRAL``** — referirse a uno mismo. El código existe y es
      válido; lo que no vale es quién lo usa.
    - **``ALREADY_REFERRED``** — ya hay un ``Referral`` para este usuario.
      ``referee`` es ``OneToOneField``, así que la base lo impediría igual;
      se comprueba antes para devolver un error legible en vez de un 500.
    """
    serializer = RedeemReferralSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    raw = serializer.validated_data['code'].strip().upper()

    referral_code = ReferralCode.objects.filter(code=raw).first()
    if referral_code is None:
        return Response(
            {'codigo_error': 'REFERRAL_CODE_NOT_FOUND',
             'detail': 'El código de referido no existe.'},
            status=status.HTTP_404_NOT_FOUND)

    if referral_code.user_id == request.user.pk:
        return Response(
            {'codigo_error': 'SELF_REFERRAL',
             'detail': 'No puedes usar tu propio código de referido.'},
            status=status.HTTP_409_CONFLICT)

    if Referral.objects.filter(referee=request.user).exists():
        return Response(
            {'codigo_error': 'ALREADY_REFERRED',
             'detail': 'Ya canjeaste un código de referido.'},
            status=status.HTTP_409_CONFLICT)

    with transaction.atomic():
        referral = Referral.objects.create(
            referrer=referral_code.user, referee=request.user, code=raw)

    return Response(
        {'id': referral.pk, 'code': referral.code,
         'status': referral.status},
        status=status.HTTP_201_CREATED)
