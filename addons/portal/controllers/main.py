"""Portal de cuenta — REST sobre las rutas ``/my/*`` de la referencia.

Adaptación fiel de ``odoo19c: addons/portal/controllers/portal.py``
(``license: LGPL-3``, medido en su ``__manifest__.py``). Mapa de rutas:

.. list-table::

   * - ``odoo19c:``
     - aquí
   * - ``/my/account`` (GET+POST)
     - ``GET|PATCH /api/v2/portal/account/``
   * - ``/my/addresses`` (GET)
     - ``GET /api/v2/portal/addresses/``
   * - ``/my/address/archive`` (POST)
     - ``POST /api/v2/portal/addresses/<pk>/archive/``
   * - ``/my/security`` (GET)
     - ``GET /api/v2/portal/security/``
   * - ``/my/security`` (POST = cambio de contraseña)
     - ``POST /api/v2/portal/security/password/``
   * - ``/my/deactivate_account`` (POST)
     - ``POST /api/v2/portal/deactivations/``

**Diferencias de población.** ``/my/addresses`` y ``/my/address/archive``
existen **sólo en 19c**; ``odoo18c: addons/portal/controllers/portal.py``
declara seis rutas y no esas dos (medido por símbolo ``route('…')`` en cada
árbol). 19 gobierna, así que se adaptan.

**Dos rutas de la referencia que NO se portan, declarado:**

- ``/my`` y ``/my/home`` — renderizan ``portal.portal_my_home``, el
  dashboard QWeb. El SPA React tiene su propia home; no hay contrato que
  adaptar.
- ``/my/counters`` — agrega los ``*_count`` que cada addon aporta con
  ``_prepare_home_portal_values``. Es un **registro de hooks**, no un
  endpoint: portarlo exige antes decidir cómo se declara ese hook en el
  monolito modular. Se deja fuera con esta nota en vez de inventar un
  agregador propio.

**Forma del error.** Las guardas de negocio se resuelven en la vista y
salen como ``Response`` con ``codigo_error`` de primer nivel — **no** como
``ValidationError`` desde el serializer. Medido: un ``ValidationError`` con
dict en ``validate()`` envuelve cada valor en lista
(``{'codigo_error': ['X']}``) y en ``validate_<campo>`` lo anida bajo el
campo (``{'a': {'codigo_error': 'X'}}``); ninguna de las dos formas cumple
el canon de ``codigo_error`` como string. Además es lo **fiel**: la
referencia ``_update_password`` *devuelve* su estructura de errores, no la
lanza.

**Autorización.** Todo aquí es *cuenta propia*: gatea por las capacidades
``account.*`` del catálogo (``base/authz_catalog.py``), que ``seed_authz``
siembra en TODOS los roles (``self_account_codes``). El sujeto sale siempre
de ``request.user`` — ningún endpoint acepta un id de usuario, así que no
hay fila ajena que acotar (el canal del dato no interviene; el de elevación
tampoco: no se usa ``su``).
"""
from django.contrib.auth import logout, update_session_auth_hash
from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.authz_ldap.models.res_users import change_password as ldap_change_password
from addons.authz_password_policy.validators import get_password_policy
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from addons.portal.controllers.serializers import (
    DeactivateAccountSerializer,
    PasswordChangeSerializer,
    PortalAccountSerializer,
    PortalAddressSerializer,
)
from addons.portal.models.res_partner import (
    can_be_edited_by,
    can_edit_country,
    can_edit_vat,
    current_partner,
)


class PortalAccountView(APIView):
    """``GET|PATCH /api/v2/portal/account/`` — ≙ ``/my/account``.

    La referencia renderiza el formulario del partner del usuario
    (``request.env.user.partner_id``) y lo guarda con el allowlist de
    campos. Aquí es el mismo partner y el mismo allowlist.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'
    # ≙ website=True en ``odoo19c: addons/portal/controllers/portal.py:190``
    is_frontend = True

    def _partner_o_404(self, request):
        partner = current_partner(request.user)
        if partner is None:
            return None
        return partner

    @extend_schema(
        summary='Ver mi contacto (≙ /my/account)',
        tags=['portal'],
        responses={
            200: PortalAccountSerializer,
            404: OpenApiResponse(description='NO_PARTNER'),
        },
    )
    def get(self, request):
        partner = self._partner_o_404(request)
        if partner is None:
            return Response(
                {'codigo_error': 'NO_PARTNER',
                 'detail': 'El usuario no tiene contacto asociado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PortalAccountSerializer(partner).data)

    @extend_schema(
        summary='Editar mi contacto (≙ POST /my/account)',
        tags=['portal'],
        request=PortalAccountSerializer,
        responses={
            200: PortalAccountSerializer,
            400: OpenApiResponse(description='VAT_NOT_EDITABLE · '
                                             'COUNTRY_NOT_EDITABLE'),
            404: OpenApiResponse(description='NO_PARTNER'),
        },
    )
    def patch(self, request):
        partner = self._partner_o_404(request)
        if partner is None:
            return Response(
                {'codigo_error': 'NO_PARTNER',
                 'detail': 'El usuario no tiene contacto asociado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PortalAccountSerializer(partner, data=request.data,
                                             partial=True)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        if 'vat' in datos and not can_edit_vat(partner):
            return Response(
                {'codigo_error': 'VAT_NOT_EDITABLE',
                 'detail': 'Sólo la entidad comercial puede editar el RFC.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'country' in datos and not can_edit_country(partner):
            return Response(
                {'codigo_error': 'COUNTRY_NOT_EDITABLE',
                 'detail': 'No se puede cambiar el país de este contacto.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return Response(serializer.data)


class PortalAddressListView(APIView):
    """``GET /api/v2/portal/addresses/`` — ≙ ``/my/addresses`` (sólo 19c).

    La referencia lista las direcciones del partner del usuario separando
    facturación de entrega. El corte se conserva: las direcciones son los
    partners **hijos** de la entidad comercial con ``type`` de dirección,
    más el propio partner (la principal, que siempre sirve para ambos).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'
    # ≙ website=True en ``odoo19c: addons/portal/controllers/portal.py:219``
    is_frontend = True

    @extend_schema(
        summary='Listar mis direcciones (≙ /my/addresses)',
        tags=['portal'],
        responses={200: PortalAddressSerializer(many=True)},
    )
    def get(self, request):
        partner = current_partner(request.user)
        if partner is None:
            return Response([])
        direcciones = ResPartner.objects.filter(
            parent=partner, active=True,
            type__in=[ResPartner.TYPE_INVOICE, ResPartner.TYPE_DELIVERY,
                      ResPartner.TYPE_OTHER],
        ).select_related('state', 'country').order_by('id')
        datos = [PortalAddressSerializer(partner).data]
        datos += PortalAddressSerializer(direcciones, many=True).data
        return Response(datos)


class PortalAddressArchiveView(APIView):
    """``POST /api/v2/portal/addresses/<pk>/archive/`` — ≙
    ``/my/address/archive`` (sólo 19c).

    Las tres guardas de la referencia se conservan en su orden:
    inexistente → 404; no editable por este cliente → 403; es la dirección
    principal → 400 (la referencia lanza ``UserError``, que su capa web
    traduce a un mensaje de negocio, no a un 403).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'
    # ≙ website=True en ``odoo19c: addons/portal/controllers/portal.py:858``
    is_frontend = True

    @extend_schema(
        summary='Archivar una dirección (≙ /my/address/archive)',
        tags=['portal'],
        request=None,
        responses={
            204: OpenApiResponse(description='Dirección archivada'),
            400: OpenApiResponse(description='MAIN_ADDRESS'),
            403: OpenApiResponse(description='ADDRESS_FORBIDDEN'),
            404: OpenApiResponse(description='ADDRESS_NOT_FOUND'),
        },
    )
    def post(self, request, pk):
        direccion = ResPartner.objects.filter(pk=pk).first()
        if direccion is None:
            return Response(
                {'codigo_error': 'ADDRESS_NOT_FOUND',
                 'detail': 'La dirección no existe.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not can_be_edited_by(direccion, request.user):
            return Response(
                {'codigo_error': 'ADDRESS_FORBIDDEN',
                 'detail': 'No puedes editar esta dirección.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        propio = current_partner(request.user)
        if propio is not None and direccion.pk == propio.pk:
            return Response(
                {'codigo_error': 'MAIN_ADDRESS',
                 'detail': 'No puedes archivar tu dirección principal.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        direccion.active = False
        direccion.save(update_fields=['active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PortalSecurityView(APIView):
    """``GET /api/v2/portal/security/`` — ≙ el GET de ``/my/security``.

    La referencia renderiza la página con dos datos de estado:
    ``allow_api_keys`` (leído de ``ir.config_parameter``) y si hay que abrir
    el modal de baja. El primero se conserva como bandera; el segundo es
    estado de UI del QWeb y no viaja.

    ``password_minimum_length`` viaja también — fold del puente
    ``auth_password_policy_portal`` de la referencia, cuyo único dominio es
    añadir esa clave a ``_prepare_portal_layout_values`` para que el
    formulario de cambio de contraseña pinte la política.
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.security'
    # ≙ website=True en ``odoo19c: addons/portal/controllers/portal.py:871``
    is_frontend = True

    @extend_schema(
        summary='Estado de seguridad de mi cuenta (≙ GET /my/security)',
        tags=['portal'],
        responses={200: OpenApiResponse(
            description='login · allow_api_keys · password_minimum_length')},
    )
    def get(self, request):
        from_param = SystemParameter.get_param('portal.allow_api_keys', '')
        return Response({
            'login': request.user.login,
            'allow_api_keys': bool(from_param),
            'password_minimum_length': get_password_policy()['minlength'],
        })


class PortalPasswordView(APIView):
    """``POST /api/v2/portal/security/password/`` — ≙ el POST de
    ``/my/security`` (``_update_password``, ``portal.py:891-913``).

    Orden conservado de la referencia:

    1. LDAP primero — si alguna configuración cambia la credencial en el
       directorio, el password local queda inutilizable y no se toca
       (``authz_ldap.res_users.change_password``, que ya porta ese ``if``).
    2. Si no, se valida la contraseña antigua y se fija la nueva.

    La referencia además **recalcula el token de sesión** para no desloguear
    al usuario tras el cambio; el equivalente nativo es
    ``update_session_auth_hash``, que hace exactamente eso con la sesión de
    Django (ADR-018: la sesión de servidor es nuestra credencial).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.password'
    # ≙ website=True en ``odoo19c: addons/portal/controllers/portal.py:871``
    is_frontend = True

    @extend_schema(
        summary='Cambiar mi contraseña (≙ POST /my/security)',
        tags=['portal'],
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description='Contraseña actualizada'),
            400: OpenApiResponse(description='PASSWORD_EMPTY · '
                                             'PASSWORD_MISMATCH · '
                                             'PASSWORD_INCORRECT'),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old = serializer.validated_data['old'].strip()
        new = serializer.validated_data['new1'].strip()
        new2 = serializer.validated_data['new2'].strip()
        user = request.user

        # Orden de ``_update_password``: primero el vacío, después la
        # comparación. El orden decide qué error ve quien deja los tres en
        # blanco, así que se conserva.
        for campo, valor in (('old', old), ('new1', new), ('new2', new2)):
            if not valor:
                return Response(
                    {'codigo_error': 'PASSWORD_EMPTY', 'campo': campo,
                     'detail': 'No se puede dejar ninguna contraseña vacía.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if new != new2:
            return Response(
                {'codigo_error': 'PASSWORD_MISMATCH', 'campo': 'new2',
                 'detail': 'La contraseña nueva y su confirmación deben ser '
                           'idénticas.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ldap_change_password(user, old, new):
            update_session_auth_hash(request, user)
            return Response({'password': True})

        if not user.check_password(old):
            return Response(
                {'codigo_error': 'PASSWORD_INCORRECT',
                 'old': 'La contraseña anterior es incorrecta; tu contraseña '
                        'no se cambió.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # ≙ ``self.env.user._change_password(new)`` — la referencia delega
        # aquí en el mismo eslabón interno que usan sus dos vías de cambio
        # (``portal.py:911`` y ``change.password.own``), y por eso el rastro
        # de auditoría es uno solo. Este endpoint lo reimplementaba con
        # ``set_password`` + ``save``, así que un cambio de credencial hecho
        # por esta vía no dejaba constancia de quién ni desde dónde.
        #
        # Se usa el eslabón INTERNO y no ``change_password(old, new)`` a
        # propósito: aquél exige y comprueba la anterior, y aquí eso ya pasó
        # arriba, con el orden de errores del portal —que no es el mismo que
        # el de ``base``—. Es exactamente la separación que la fuente diseña.
        user._change_password(new)
        update_session_auth_hash(request, user)
        return Response({'password': True})


class PortalDeactivationView(APIView):
    """``POST /api/v2/portal/deactivations/`` — ≙ ``/my/deactivate_account``.

    Las dos pruebas de la referencia, en su orden: ``validation`` debe
    igualar el *login*, y después la contraseña debe validar. Sólo entonces
    se desactiva la cuenta, se registra la solicitud de baja
    (``res.users.deletion``, ≙ ``_deactivate_portal_user``) y se cierra la
    sesión (≙ ``request.session.logout()``).
    """

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.deactivate'
    # ≙ website=True en ``odoo19c: addons/portal/controllers/portal.py:914``
    is_frontend = True

    @extend_schema(
        summary='Dar de baja mi cuenta (≙ /my/deactivate_account)',
        tags=['portal'],
        request=DeactivateAccountSerializer,
        responses={
            204: OpenApiResponse(description='Cuenta dada de baja'),
            400: OpenApiResponse(description='VALIDATION_MISMATCH · '
                                             'PASSWORD_INCORRECT'),
        },
    )
    def post(self, request):
        serializer = DeactivateAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if serializer.validated_data['validation'] != user.login:
            return Response(
                {'codigo_error': 'VALIDATION_MISMATCH',
                 'validation': 'Escribe tu usuario exactamente para '
                               'confirmar la baja.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.check_password(serializer.validated_data['password']):
            return Response(
                {'codigo_error': 'PASSWORD_INCORRECT',
                 'password': 'La contraseña es incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Delega en el recordset — ≙ ``request.env.user
            # ._deactivate_portal_user()`` de la fuente
            # (``odoo19c: addons/portal/controllers/portal.py``). Antes esta
            # vista abría el método a mano y sólo hacía dos de sus seis
            # mitades: archivaba y encolaba. Faltaban la guarda de clase, la
            # ofuscación del login, la inutilización de la contraseña, el
            # retiro de las claves de API, el archivado del partner y la causa
            # ``deactivated_reason``, sin la cual la reactivación por email no
            # distingue una baja voluntaria de una suspensión.
            ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
            logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
