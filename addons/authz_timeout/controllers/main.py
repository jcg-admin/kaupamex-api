"""Vistas — ``addons.authz_timeout`` (confirmar identidad al vencer el candado).

Adaptación de ``auth_timeout/controllers/main.py`` de Odoo
(``odoo-tools@abe4040ec1``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 de 3
===================================

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Símbolo (línea)
     - Aquí
     - Ruta
   * - ``check_identity`` (``:6``)
     - ``check_identity_state``
     - ``GET  …/timeout/check-identity/``
   * - ``check_identity_session`` (``:15``)
     - ``check_identity_submit``
     - ``POST …/timeout/session/check-identity/``
   * - ``_send_totp_mail_code`` (``:20``)
     - ``send_totp_mail_code_view``
     - ``POST …/timeout/send-totp-mail-code/``

**Las dos primeras son rutas distintas, como en la fuente** — no un `GET` y
un `POST` sobre la misma. La fuente separa la página (``/check-identity``)
del receptor del formulario (``/session/check-identity``), y esa separación
se conserva: el 403 apunta a la primera, y el cliente sabe que envía a la
segunda, igual que la página de la fuente sabe a qué ruta hace su ``rpc``.

Divergencia del primero — página HTML contra estado JSON
=========================================================

La fuente devuelve ``request.render("auth_timeout.check_identity", …)``: una
**página** que aloja el componente OWL del diálogo. Aquí no hay plantilla que
renderizar —el cliente es React y vive en ``kaupamex-ui``—, así que el
símbolo se porta con su papel y no con su forma: entrega **el estado que el
diálogo necesita** (qué métodos admite este usuario, si hace falta segundo
factor), que es exactamente lo que el ``owl-component`` de la fuente recibe
por ``t-att-props``.

Es el mismo dato que el 403 ``CHECK_IDENTITY_REQUIRED`` ya lleva en su
cuerpo; el endpoint existe para el caso en que el cliente lo perdió (recarga
de página, navegación directa a la ruta de confirmación).

El parámetro ``redirect`` de la fuente **no se porta**: existe para que la
página sepa a dónde volver tras confirmar. En un cliente REST el destino lo
conserva el propio cliente, que reintenta la petición que recibió el 403.

Autorización
============

Los tres van con ``account.security`` — la capacidad de **cuenta propia** que
``seed_authz`` siembra en TODOS los roles (DEC-ENF-01), y la misma con que
``authz_totp_mail`` gobierna su envío/verificación de código. Nunca
``IsAuthenticated`` a secas, que saltaría el modelo de capacidades (DEC-11).

Y los tres declaran ``check_identity = False`` — el atributo que
``models/ir_http.py::_view_declares_check_identity`` lee. Sin él, el
middleware exigiría confirmar identidad para llegar al endpoint con el que se
confirma la identidad: un candado sobre su propia llave. La fuente lo declara
igual, en las tres rutas (``check_identity=False`` en ``:8``, ``:15``,
``:20``).
"""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.authz_timeout.controllers.serializers import CheckIdentitySerializer
from addons.authz_timeout.models.ir_http import _check_identity, _must_check_identity
from addons.authz_totp_mail.models.res_users import _send_totp_mail_code

_TAGS = ['authz-candado-tiempo']
_CAP = 'account.security'


@extend_schema(
    tags=_TAGS,
    summary='Estado del candado: qué métodos admite este usuario',
    responses={200: OpenApiResponse(
        description='{user_id, login, auth_methods, mfa}')},
)
@api_view(['GET'])
@require_capability(_CAP)
def check_identity_state(request):
    """GET — ≙ ``check_identity`` (``main.py:6``), sin la página.

    Devuelve lo que el diálogo de confirmación necesita para dibujarse.
    """
    estado = _check_identity(request, None) or {}
    pendiente = _must_check_identity(request) or {}
    estado['mfa'] = bool(pendiente.get('mfa'))
    return Response(estado)


@extend_schema(
    tags=_TAGS,
    summary='Confirmar identidad con una credencial',
    request=CheckIdentitySerializer,
    responses={
        200: OpenApiResponse(
            description='{} si quedó confirmada; {mfa: true, auth_methods} si '
                        'falta el segundo factor'),
        400: OpenApiResponse(description='INVALID_TOKEN · INVALID_CREDENTIAL'),
        401: OpenApiResponse(description='CHECK_IDENTITY_FAILED'),
    },
)
@api_view(['POST'])
@require_capability(_CAP)
def check_identity_submit(request):
    """POST — ≙ ``check_identity_session`` (``main.py:15``).

    La fuente no distingue credencial inválida de confirmación completa: su
    ``_check_credentials`` levanta ``AccessDenied`` y el despachador la
    convierte. Aquí ``_check_credential`` devuelve ``None`` en ese caso, así
    que la vista lo sella como **401 ``CHECK_IDENTITY_FAILED``** — mismo
    desenlace, con código propio para que el cliente distinga "credencial
    incorrecta" de "hace falta un segundo factor".
    """
    serializer = CheckIdentitySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    credential = dict(serializer.validated_data)

    if not credential:
        return Response(_check_identity(request, None) or {})

    antes = request.session.get('identity-check-last')
    resultado = _check_identity(request, credential)
    if resultado is not None:
        return Response(resultado)

    # ``_check_identity`` devuelve ``None`` en dos casos opuestos: credencial
    # rechazada, y confirmación completa. Los separa el sello que sólo el
    # segundo escribe.
    if request.session.get('identity-check-last') == antes:
        return Response(
            {'codigo_error': 'CHECK_IDENTITY_FAILED',
             'detail': 'No pudimos verificar esa credencial.'},
            status=401,
        )
    return Response({})


@extend_schema(
    tags=_TAGS,
    summary='Reenviar el código de segundo factor por correo',
    request=None,
    responses={200: OpenApiResponse(description='{sent: true}')},
)
@api_view(['POST'])
@require_capability(_CAP)
def send_totp_mail_code_view(request):
    """POST — ≙ ``_send_totp_mail_code`` (``main.py:20``).

    La fuente llama ``self.env.user._send_totp_mail_code()``; aquí el mismo
    mecanismo es la función de módulo ``_send_totp_mail_code(user)`` de
    ``authz_totp_mail``, que es donde este árbol lo declara.
    """
    _send_totp_mail_code(request.user)
    return Response({'sent': True})


# El atributo que ``_view_declares_check_identity`` lee. Se fija sobre la
# función porque ``@api_view`` devuelve un envoltorio, y es la forma que ese
# lector ya contempla (función · ``.cls`` · ``.view_class``).
for _vista in (check_identity_state, check_identity_submit,
               send_totp_mail_code_view):
    _vista.check_identity = False
