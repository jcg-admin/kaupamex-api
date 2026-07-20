"""
Views — addons.users

Sprint 1: RegisterView
Sprint 2: ProfileView, AddressViewSet, ChangePasswordView
Sprint 3: Password reset, email verification, admin user management
Sprint 4: DeactivateAccountView (UC-AUTH-16)
Sprint 5: LogoutAllSessionsView (UC-AUTH-18)
"""
# stdlib + Django
import logging
import uuid

from django.contrib.auth import get_user_model, login as django_login
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability

from .session_tracking import record_user_session
from .audit import audit_log_auth
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.types import OpenApiTypes as OAT
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from addons.cart.models import Cart, SavedCart
from addons.mail.models import NotificationPreference
from addons.website.models import SearchEntry
from addons.website_sale_wishlist.models import WishlistItem
from .models import Address, AuthEvent, EmailVerificationToken, PasswordResetToken, UserDeactivationEvent
from .serializers import AddressSerializer, ChangePasswordSerializer, EmailVerificationSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, ProfileSerializer, RegisterSerializer, ResendVerificationSerializer, UpdateProfileSerializer
from .tokens_email import check_rate_limit, create_password_reset_token, create_verification_token, invalidate_all_sessions, send_password_reset_email, send_verification_email, validate_password_reset_token, validate_verification_token
from addons.authz.services import assign_buyer_role, is_superadmin
from addons.auth_signup.policy import password_reset_enabled, signup_open

# DRF + plugins


# Local


User = get_user_model()
logger = logging.getLogger('apps')


def _merge_anon_cart_into_user(user, cart_token):
    """H-CART-01: fusiona el carrito anónimo (cart_token) en el carrito del
    usuario recién registrado.

    El X-Cart-Token es memory-only en el cliente (DEC-BC-07) y se pierde cuando
    el enlace de activación del email abre una carga de página nueva. Asociando
    el carrito anónimo a la cuenta AQUÍ (en el registro, cuando el token aún
    existe), los productos sobreviven a la verificación por email y siguen en el
    carrito tras el auto-login.
    """
    if not cart_token:
        return
    try:
        token = uuid.UUID(str(cart_token))
    except (ValueError, TypeError, AttributeError):
        return
    anon = Cart.objects.filter(cart_token=token, user__isnull=True).first()
    if anon is None:
        return
    try:
        user_cart, _ = Cart.objects.get_or_create(user=user)
        user_cart.merge(anon)
    except Exception:
        # Loud-log sin re-raise (DEC-DOC-008): una falla al fusionar el carrito
        # no debe romper el registro, que es la operación crítica.
        logger.warning('anon cart merge on register failed user_id=%s', user.pk, exc_info=True)


class RegisterView(APIView):
    """POST /api/v1/auth/register/ — UC-AUTH-01."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(
        summary='Registrar cuenta de comprador',
        description=(
            'Crea una cuenta nueva con is_active=False hasta verificar el email '
            '(UC-AUTH-01). El email se normaliza a minusculas. Los mensajes de '
            'unicidad son intencionalmente ambiguos para prevenir enumeracion de usuarios.'
        ),
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(description='Cuenta creada. Se envia email de verificacion.'),
            400: OpenApiResponse(description='Error de validacion (formato o unicidad).'),
        },
        tags=['auth'],
    )
    def post(self, request):
        # UC-AUTH-01 Alt-A: cuando el email ya existe en BD, el flujo se
        # ramifica segun users_user.deactivated_reason. La respuesta
        # publica es ambigua en A.2/A.3 (no filtra estado de cuenta)
        # pero explicita en A.1 (cuenta activa) por necesidad UX.
        email = (request.data.get('email') or '').lower().strip()
        # audit-log-eventos-auth-register DEC-ALR-2: emit ATTEMPT
        # SIEMPRE para signal de account enumeration probes.
        audit_log_auth(
            None, AuthEvent.ACTION_REGISTER_ATTEMPT, request,
            extra={'email_present': bool(email)},
        )

        # authz_signup (DEC-01, ~auth_signup de Odoo): el auto-registro público
        # es una política editable en caliente (L2), no un comportamiento
        # cableado. Si el operador cerró el registro, 403 SIGNUP_CLOSED.
        if not signup_open():
            return Response(
                {'codigo_error': 'SIGNUP_CLOSED',
                 'detail': 'El registro de nuevas cuentas está deshabilitado.'},
                status=403,
            )

        existing = User.objects.filter(email__iexact=email).first() if email else None

        if existing is not None:
            CREATED_RESPONSE = Response(
                {'message': 'Cuenta creada. Revisa tu email para activarla.'},
                status=201,
            )
            # Alt-A.1: cuenta activa -> 409 Conflict (UC-AUTH-01 FR-AUTH-01.03).
            if existing.is_active:
                # DEC-ALR-3: REGISTER_FAIL sin leak (reason generico).
                audit_log_auth(
                    None, AuthEvent.ACTION_REGISTER_FAIL, request,
                    reason='email_invalid',
                )
                return Response(
                    {'email': [
                        'Esa cuenta ya esta registrada. Inicia sesion '
                        'o recupera tu contrasena si la olvidaste.'
                    ]},
                    status=409,
                )
            # Alt-A.2: inactiva reactivable (unverified o self_deleted)
            # -> generar token + reenviar email. Mismo response shape que
            # una cuenta nueva para no filtrar el estado.
            # DEC-ALR-5: NO emit REGISTER_SUCCESS (no se crea user nuevo).
            if existing.deactivated_reason in User.DEACTIVATION_REASONS_REACTIVABLE_BY_EMAIL:
                plain = create_verification_token(existing)
                send_verification_email(
                    existing, plain, next_path=request.data.get('next', ''),
                )
                _merge_anon_cart_into_user(existing, request.data.get('cart_token'))
                return CREATED_RESPONSE
            # Alt-A.3: suspendida por admin (o motivo desconocido) ->
            # no enviar email, retornar response indistinguible.
            return CREATED_RESPONSE

        # Camino estandar: email no existe, crear cuenta nueva.
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # DEC-AUTHZ-BUYER: asignar el rol 'comprador' para que su menú de
            # cuenta (dinámico, audience='account') aparezca al iniciar sesión.
            # Tolerante si authz no está sembrado (no rompe el registro).
            assign_buyer_role(user)
            # H-CART-01: fusionar el carrito anónimo en la cuenta nueva mientras
            # el cart_token aún existe (se pierde al abrir el enlace de email).
            _merge_anon_cart_into_user(user, request.data.get('cart_token'))
            # DEC-ALR-4: REGISTER_SUCCESS convive con
            # UserDeactivationEvent(source='register') ya
            # existente en RegisterSerializer.save().
            audit_log_auth(
                user, AuthEvent.ACTION_REGISTER_SUCCESS, request,
            )
            return Response(
                {'message': 'Cuenta creada. Revisa tu email para activarla.'},
                status=201,
            )
        # DEC-ALR-3: reason = primer field error name + '_invalid'
        # (sin leak del value ni del error message completo).
        first_field = next(iter(serializer.errors.keys()), 'unknown')
        audit_log_auth(
            None, AuthEvent.ACTION_REGISTER_FAIL, request,
            reason=f'{first_field}_invalid',
        )
        return Response(serializer.errors, status=400)


class ProfileView(APIView):
    """GET/PATCH /api/v1/auth/profile/ — UC-AUTH-05 y UC-AUTH-06."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'

    @extend_schema(
        summary='Ver perfil del comprador',
        description=(
            'Retorna los datos del perfil del comprador autenticado: datos personales, '
            'avatar_url absoluta, profile_completeness (0-100 en multiplos de 20) y '
            'pending_fields con los campos opcionales pendientes.'
        ),
        responses={
            200: ProfileSerializer,
            401: OpenApiResponse(description='No autenticado.'),
        },
        tags=['auth'],
    )
    def get(self, request):
        serializer = ProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        summary='Editar perfil del comprador',
        description=(
            'Actualiza first_name, last_name, phone y/o avatar. '
            'El email y el username no son editables en este endpoint. '
            'El avatar se valida (JPEG/PNG/WebP), redimensiona a 800x800 '
            'y se convierte a WebP.'
        ),
        request=UpdateProfileSerializer,
        responses={
            200: ProfileSerializer,
            400: OpenApiResponse(description='Error de validacion (formato de avatar u otro).'),
            401: OpenApiResponse(description='No autenticado.'),
        },
        tags=['auth'],
    )
    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        if serializer.is_valid():
            user = serializer.save()
            return Response(ProfileSerializer(user, context={'request': request}).data)
        return Response(serializer.errors, status=400)


class AddressViewSet(ModelViewSet):
    """
    /api/v1/auth/addresses/ — UC-AUTH-07: Gestionar Direcciones de Envio.

    GET    /addresses/      — listar las direcciones del usuario autenticado
    POST   /addresses/      — crear nueva direccion (max 5)
    PATCH  /addresses/{id}/ — editar una direccion propia
    DELETE /addresses/{id}/ — eliminar una direccion propia
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'addresses'
    serializer_class = AddressSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    # queryset estatico requerido por drf-spectacular para inferir el tipo del path param.
    # get_queryset() lo sobreescribe en runtime para filtrar por usuario.
    queryset = Address.objects.none()

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    def _do_destroy(self, request, *args, **kwargs):
        """Al eliminar la default, promover la siguiente como default."""
        addr = self.get_object()
        was_default = addr.is_default
        addr_id = addr.pk
        addr.delete()
        if was_default:
            next_addr = Address.objects.filter(user=request.user).order_by('-pk').first()
            if next_addr:
                next_addr.is_default = True
                next_addr.save(update_fields=['is_default', 'updated_at'])
        audit_log_auth(request.user, AuthEvent.ACTION_ADDRESS_DELETED, request,
                       extra={'address_id': addr_id})
        return Response(status=204)

    @extend_schema(
        summary='Listar direcciones de envio',
        responses={200: AddressSerializer(many=True)},
        tags=['auth'],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary='Crear direccion de envio',
        request=AddressSerializer,
        responses={
            201: AddressSerializer,
            400: OpenApiResponse(description='Error de validacion.'),
            422: OpenApiResponse(description='Limite de 5 direcciones alcanzado.'),
        },
        tags=['auth'],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if any('limite_direcciones' in str(e) for e in errors.values()):
                msg = errors.get('non_field_errors', ['Limite de direcciones alcanzado.'])[0]
                return Response(
                    {'codigo_error': 'ADDRESS_LIMIT_EXCEEDED', 'detail': str(msg)},
                    status=422,
                )
            return Response(errors, status=400)
        self.perform_create(serializer)
        audit_log_auth(request.user, AuthEvent.ACTION_ADDRESS_CREATED, request,
                       extra={'address_id': serializer.instance.pk})
        return Response(serializer.data, status=201)

    @extend_schema(
        summary='Editar direccion de envio',
        parameters=[OpenApiParameter('id', OAT.INT, OpenApiParameter.PATH)],
        request=AddressSerializer,
        responses={200: AddressSerializer},
        tags=['auth'],
    )
    def partial_update(self, request, *args, **kwargs):
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(obj, '_prefetched_objects_cache', None):
            obj._prefetched_objects_cache = {}
        audit_log_auth(request.user, AuthEvent.ACTION_ADDRESS_UPDATED, request,
                       extra={'address_id': obj.pk})
        return Response(serializer.data)

    @extend_schema(
        summary='Eliminar direccion de envio',
        parameters=[OpenApiParameter('id', OAT.INT, OpenApiParameter.PATH)],
        responses={204: None},
        tags=['auth'],
    )
    def destroy(self, request, *args, **kwargs):
        return self._do_destroy(request, *args, **kwargs)

    @extend_schema(
        summary='Marcar direccion como predeterminada',
        description=(
            'Marca la direccion indicada como is_default=True y desmarca '
            'cualquier otra del mismo usuario. UC-AUTH-07.'
        ),
        parameters=[OpenApiParameter('id', OAT.INT, OpenApiParameter.PATH)],
        request=None,
        responses={
            200: AddressSerializer,
            404: OpenApiResponse(description='Direccion no encontrada.'),
        },
        tags=['auth'],
    )
    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        addr = self.get_object()
        addr.is_default = True
        addr.save()  # el save() del modelo desmarca las demas atomicamente
        audit_log_auth(request.user, AuthEvent.ACTION_ADDRESS_DEFAULT, request,
                       extra={'address_id': addr.pk})
        return Response(self.get_serializer(addr).data, status=200)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/ — UC-AUTH-08."""
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.password'
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "change_password"

    @extend_schema(
        summary='Cambiar contrasena',
        description=(
            'Verifica la contrasena actual antes de establecer la nueva. '
            'La nueva debe cumplir los validadores de Django (min 8 chars, '
            'no muy comun, no similar al username). '
            'UC-AUTH-08 PARTE 8.2 (DEC-AUM-01): invalida todas las '
            'sesiones activas del usuario tras el cambio para cerrar '
            'el vector account-takeover.'
        ),
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description='Contrasena cambiada exitosamente.'),
            400: OpenApiResponse(description='Contrasena actual incorrecta o nueva invalida.'),
            401: OpenApiResponse(description='No autenticado.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response({'detail': 'Password changed successfully.'})
        errors = serializer.errors
        if 'current_password' in errors:
            return Response(
                {'codigo_error': 'CURRENT_PASSWORD_INCORRECT',
                 'detail': str(errors['current_password'][0])},
                status=400,
            )
        if 'non_field_errors' in errors:
            return Response(
                {'codigo_error': 'PASSWORD_NOT_CHANGED',
                 'detail': str(errors['non_field_errors'][0])},
                status=400,
            )
        if 'new_password' in errors:
            return Response(
                {'codigo_error': 'INVALID_PASSWORD',
                 'detail': str(errors['new_password'][0])},
                status=400,
            )
        if 'new_password_confirm' in errors:
            return Response(
                {'codigo_error': 'PASSWORDS_DO_NOT_MATCH',
                 'detail': str(errors['new_password_confirm'][0])},
                status=400,
            )
        return Response({'codigo_error': 'INVALID_PAYLOAD', 'detail': str(errors)}, status=400)


# ─── Sprint 3 ──────────────────────────────────────────────────────


class PasswordResetRequestView(APIView):
    """POST /api/v1/auth/password-reset/ — UC-AUTH-09 Fase 1."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(
        summary='Solicitar recuperacion de contrasena',
        description=(
            'Genera un token de recuperacion y envia un email al usuario. '
            'Siempre retorna 200 independientemente de si el email existe '
            '(FR-AUTH-09.01 — previene enumeracion). Rate limit: 3/hora/email.'
        ),
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(description='Email enviado si la cuenta existe.'),
            400: OpenApiResponse(description='Formato de email invalido.'),
            429: OpenApiResponse(description='Limite de solicitudes alcanzado.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        # authz_signup (DEC-01, ~auth_signup de Odoo): el reset desde login es
        # una política editable en caliente (L2), no un comportamiento cableado.
        if not password_reset_enabled():
            return Response(
                {'codigo_error': 'PASSWORD_RESET_DISABLED',
                 'detail': 'La recuperación de contraseña está deshabilitada.'},
                status=403,
            )

        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']

        if not check_rate_limit(email):
            return Response(
                {'detail': 'Demasiadas solicitudes. Intenta de nuevo en 1 hora.'},
                status=429,
            )

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
            plain = create_password_reset_token(user)
            send_password_reset_email(user, plain)
        except User.DoesNotExist:
            pass  # silent OK because no revela si el email existe (anti-enumeracion)

        return Response(
            {'message': 'Si ese email esta registrado, recibiras las instrucciones.'}
        )


class PasswordResetConfirmView(APIView):
    """POST /api/v1/auth/password-reset/confirm/ — UC-AUTH-09 Fase 2."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_confirm"

    @extend_schema(
        summary='Confirmar recuperacion de contrasena',
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(description='Contrasena restablecida. Sesiones invalidadas.'),
            400: OpenApiResponse(description='Token invalido, expirado o contrasena debil.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            token_obj = validate_password_reset_token(
                serializer.validated_data['token']
            )
        except ValueError as e:
            return Response({'token': str(e)}, status=400)

        with transaction.atomic():
            user = token_obj.user
            user.set_password(serializer.validated_data['new_password'])
            user.save(update_fields=['password'])
            token_obj.used_at = timezone.now()
            token_obj.save(update_fields=['used_at', 'updated_at'])
            invalidate_all_sessions(user)

        return Response({'message': 'Contrasena restablecida exitosamente. Inicia sesion.'})


class EmailVerifyView(APIView):
    """POST /api/v1/auth/verify-email/ — UC-AUTH-10."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verify"

    @extend_schema(
        summary='Verificar email y activar cuenta',
        request=EmailVerificationSerializer,
        responses={
            200: OpenApiResponse(description='Cuenta activada o ya estaba activa.'),
            400: OpenApiResponse(description='Token invalido o expirado.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            token_obj = validate_verification_token(serializer.validated_data['token'])
        except ValueError as e:
            return Response(
                {'codigo_error': getattr(e, 'error_code', 'TOKEN_INVALID'), 'detail': str(e)},
                status=400,
            )
        except Exception:
            logger.error('EmailVerifyView: error inesperado al validar token', exc_info=True)
            return Response(
                {'codigo_error': 'SERVER_ERROR', 'detail': 'Error interno al verificar el token.'},
                status=500,
            )

        if token_obj is None:
            return Response({'message': 'Tu cuenta ya esta activa. Puedes iniciar sesion.'})

        with transaction.atomic():
            user = token_obj.user
            user.is_active = True
            # GAP-3 cierre: limpiar la causa al reactivar para que el
            # estado de la cuenta sea consistente despues del click.
            user.deactivated_reason = None
            user.deactivated_at = None
            user.save(update_fields=[
                'is_active', 'deactivated_reason', 'deactivated_at',
            ])
            token_obj.used_at = timezone.now()
            token_obj.save(update_fields=['used_at', 'updated_at'])
            # ADR-020: invariante "registrado y validado recibe comprador".
            # Idempotente/tolerante: garantiza el rol tambien al validar, por si
            # el registro no lo asigno (rol aun no sembrado, alta por import, etc.).
            assign_buyer_role(user)

        # UX (ADR-018): auto-login por sesion tras verificar. Hacer clic en el
        # enlace de un solo uso prueba control del correo = control de la cuenta
        # (mismo nivel de confianza que el reset de contrasena), asi que se
        # establece la sesion y el SPA aterriza en 'next' sin re-loguearse. El
        # backend se pasa explicito porque el user no se autentico via un backend
        # de auth (se valido por el token del email).
        django_login(
            request, user,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        # UC-AUTH-17 (H-16): registra la sesion (IP/dispositivo).
        record_user_session(request, user)
        return Response({
            'message': 'Cuenta activada exitosamente.',
            'isAuthenticated': True,
            'user': {
                'id':         user.pk,
                'username':   user.email,
                'email':      user.email,
                'first_name': user.first_name,
                'last_name':  user.last_name,
                'is_staff':   is_superadmin(user),
                'avatar_url': user.get_avatar_url(),
            },
        })


class ResendVerificationView(APIView):
    """POST /api/v1/auth/resend-verification/ — UC-AUTH-10."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resend_verification"

    @extend_schema(
        summary='Reenviar email de verificacion',
        request=ResendVerificationSerializer,
        responses={
            200: OpenApiResponse(description='Email reenviado si la cuenta existe y no esta activa.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email__iexact=email, is_active=False)
            # UC-AUTH-01 Alt-A.3: cuentas suspendidas por admin NO se
            # reactivan por email. UC-AUTH-14 es el unico camino.
            # El mensaje al cliente es identico al caso DoesNotExist
            # para no filtrar el estado de la cuenta.
            if user.deactivated_reason in User.DEACTIVATION_REASONS_REACTIVABLE_BY_EMAIL:
                plain = create_verification_token(user)
                send_verification_email(
                    user, plain, next_path=request.data.get('next', ''),
                )
            # else: silencio deliberado (suspended).
        except User.DoesNotExist:
            pass  # silent OK because no revela el estado de la cuenta (anti-enumeracion)

        return Response(
            {'message': 'Si ese email esta pendiente de verificacion, recibiras un nuevo enlace.'}
        )


class DeactivateAccountSerializer(drf_serializers.Serializer):
    """Payload de POST /api/v1/auth/me/deactivate/ — UC-AUTH-16."""
    password = drf_serializers.CharField(write_only=True)


class DeactivateAccountView(APIView):
    """POST /api/v1/auth/me/deactivate/ — UC-AUTH-16 (Dar de Baja la Propia Cuenta).

    Soft-delete logico iniciado por el propio usuario. Pone
    is_active=False y registra la causa (self_deleted) y el
    timestamp. Invalida refresh tokens activos.

    Postcondiciones: la cuenta puede reactivarse via
    UC-AUTH-01 Alt-A.2 (re-registro con mismo email -> reenvio
    de email de verificacion) o via UC-AUTH-14 (admin).
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.deactivate'

    @extend_schema(
        summary='Dar de baja la propia cuenta (UC-AUTH-16)',
        description=(
            'Soft-delete logico iniciado por el comprador autenticado. '
            'Requiere reautenticacion con la contrasena de la sesion '
            'actual. is_active pasa a False con deactivated_reason='
            "'self_deleted'. No elimina datos. La cuenta puede "
            'reactivarse despues via UC-AUTH-01 Alt-A.2.'
        ),
        request=DeactivateAccountSerializer,
        responses={
            200: OpenApiResponse(description='Cuenta dada de baja.'),
            400: OpenApiResponse(description='Contrasena incorrecta o payload invalido.'),
            401: OpenApiResponse(description='No autenticado.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        # Rate-limit por user.pk para evitar abuso de sesion robada
        # repitiendo intentos hasta acertar la password. La key se hashea
        # internamente; el prefijo "deactivate:" la separa del bucket de
        # password reset.
        if not check_rate_limit(
            f'deactivate:{request.user.pk}',
            max_requests=5, window=3600,
        ):
            return Response(
                {'detail': 'Demasiados intentos. Intenta en 1 hora.'},
                status=429,
            )

        serializer = DeactivateAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        user = request.user
        if not user.check_password(serializer.validated_data['password']):
            return Response({'detail': 'Contrasena incorrecta.'}, status=400)

        with transaction.atomic():
            user.is_active = False
            user.deactivated_reason = User.DEACTIVATION_SELF_DELETED
            user.deactivated_at = timezone.now()
            user.save(update_fields=[
                'is_active', 'deactivated_reason', 'deactivated_at',
            ])
            # Invalidar tokens pendientes para que enlaces viejos no
            # sirvan tras la baja. used_at = NOW marca como consumido.
            now = timezone.now()
            EmailVerificationToken.objects.filter(
                user=user, used_at__isnull=True,
            ).update(used_at=now, updated_at=now)
            PasswordResetToken.objects.filter(
                user=user, used_at__isnull=True,
            ).update(used_at=now, updated_at=now)
            invalidate_all_sessions(user)
            # FU-4: politica de limpieza en self-delete.
            # Se ELIMINAN fisicamente los datos volatiles que no tienen
            # relevancia fiscal y que el usuario probablemente prefiere
            # que no persistan tras la baja:
            #   - cart_cart + cart_cart_item (carrito activo)
            #   - cart_saved_cart + cart_saved_cart_item (carritos guardados)
            #   - wishlist_item (hereda SoftDeleteModel — hard_delete()
            #     fuerza borrado fisico, no soft)
            #   - search_history_entry (historial personal de busquedas)
            #   - notifications_preference (preferencias personales)
            #
            # Se CONSERVAN (transaccionales/fiscales):
            #   - orders_order + relacionados (audit fiscal)
            #   - payments_payment, refunds, gateway_event
            #   - returns_*, support_ticket_* (audit cliente)
            #   - users_address (referenciado desde orders_order_address
            #     snapshot, conservar la fila original facilita lookup)
            #   - users_deactivation_event (audit append-only)
            Cart.objects.filter(user=user).delete()
            SavedCart.objects.filter(user=user).delete()
            # WishlistItem.all_objects + hard_delete: bypassa el
            # soft-delete del modelo (queremos borrado fisico).
            for item in WishlistItem.all_objects.filter(user=user):
                item.hard_delete()
            SearchEntry.objects.filter(user=user).delete()
            NotificationPreference.objects.filter(user=user).delete()
            # GAP 10: audit log del evento (append-only).
            UserDeactivationEvent.objects.create(
                user=user,
                reason=User.DEACTIVATION_SELF_DELETED,
                source=UserDeactivationEvent.SOURCE_SELF,
                actor=None,
            )

        return Response({'message': 'Tu cuenta ha sido dada de baja.'}, status=200)


class LogoutAllSessionsView(APIView):
    """POST /api/v1/auth/logout-all/ — UC-AUTH-18 (Cerrar todas las sesiones).

    Invalida todos los refresh tokens activos del usuario autenticado.
    El access token actual sigue siendo valido hasta su expiracion (JWT
    sin estado), pero ningun refresh token podra generar un nuevo access
    token desde ese momento.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'

    @extend_schema(
        summary='Cerrar todas las sesiones activas (UC-AUTH-18)',
        description=(
            'Invalida todos los refresh tokens activos del usuario. '
            'El access token actual expira naturalmente. '
            'Util cuando el usuario sospecha acceso no autorizado.'
        ),
        request=None,
        responses={
            200: OpenApiResponse(description='Todas las sesiones cerradas.'),
            401: OpenApiResponse(description='No autenticado.'),
        },
        tags=['auth'],
    )
    def post(self, request):
        # H-09: preservar la sesion en curso — el contrato de la UI es
        # "cerrar todas las sesiones EXCEPTO la actual" (SecurityPage).
        # Sin keep_session_key se borraba tambien la del propio llamador.
        invalidate_all_sessions(
            request.user, keep_session_key=request.session.session_key,
        )
        return Response(
            {'message': 'Se cerraron las demas sesiones.'}, status=200,
        )


# AdminUserPagination definicion canonica vive en admin_views.py
# (donde AdminUserViewSet la usa). Aqui solo quedaba huerfana.


# AdminUserListView eliminado (era codigo muerto): no estaba registrado
# en urlpatterns. El endpoint GET /api/v1/admin/users/ lo sirve
# AdminUserViewSet en admin_views.py via router DefaultRouter.
# La logica de filtros (incluido el nuevo ?deactivated_reason=) vive
# alli — ver admin_views.AdminUserViewSet.get_queryset.


class EmailVerificationV2View(APIView):
    """POST /api/v2/auth/email-verifications/ — Tier B merged endpoint.

    Merges two v1 endpoints into one:
    - Body contains 'token' key  → delegate to EmailVerifyView (verify).
    - Body contains 'email' key  → delegate to ResendVerificationView (resend).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        if 'token' in request.data:
            return EmailVerifyView().post(request)
        return ResendVerificationView().post(request)


class PasswordResetV2View(APIView):
    """POST /api/v2/auth/password-resets/ — Tier A."""
    permission_classes = [AllowAny]

    def post(self, request):
        return PasswordResetRequestView().post(request)


class PasswordResetConfirmV2View(APIView):
    """POST /api/v2/auth/password-resets/confirm/ — Tier A."""
    permission_classes = [AllowAny]

    def post(self, request):
        return PasswordResetConfirmView().post(request)


class DeactivateMeV2View(APIView):
    """DELETE /api/v2/auth/me/ — Tier B.

    v1 used POST /auth/me/deactivate/; v2 uses DELETE /auth/me/.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.deactivate'

    def delete(self, request):
        return DeactivateAccountView().post(request)


class DeleteSessionsV2View(APIView):
    """DELETE /api/v2/auth/sessions/ — Tier B.

    v1 used POST /auth/logout-all/; v2 uses DELETE /auth/sessions/.
    """
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'account.profile'

    def delete(self, request):
        return LogoutAllSessionsView().post(request)
