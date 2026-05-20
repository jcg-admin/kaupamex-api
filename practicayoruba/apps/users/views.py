"""
Views — apps.users

Sprint 1: RegisterView
Sprint 2: ProfileView, AddressViewSet, ChangePasswordView
"""
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from drf_spectacular.types import OpenApiTypes as OAT
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import serializers as drf_serializers

from .models import Address
from .serializers import (
    RegisterSerializer,
    ProfileSerializer,
    UpdateProfileSerializer,
    ChangePasswordSerializer,
    AddressSerializer,
)


class RegisterView(APIView):
    """POST /api/v1/auth/register/ — UC-AUTH-01."""
    permission_classes = [AllowAny]

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
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'message': 'Cuenta creada. Revisa tu email para activarla.',
                 'user_id': user.pk},
                status=201,
            )
        return Response(serializer.errors, status=400)


class ProfileView(APIView):
    """GET/PATCH /api/v1/auth/profile/ — UC-AUTH-05 y UC-AUTH-06."""
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]
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
        addr.delete()
        if was_default:
            next_addr = Address.objects.filter(user=request.user).first()
            if next_addr:
                next_addr.is_default = True
                next_addr.save(update_fields=['is_default'])
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
                return Response(errors, status=422)
            return Response(errors, status=400)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)

    @extend_schema(
        summary='Editar direccion de envio',
        parameters=[OpenApiParameter('id', OAT.INT, OpenApiParameter.PATH)],
        request=AddressSerializer,
        responses={200: AddressSerializer},
        tags=['auth'],
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

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
        return Response(self.get_serializer(addr).data, status=200)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/ — UC-AUTH-08."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Cambiar contrasena',
        description=(
            'Verifica la contrasena actual antes de establecer la nueva. '
            'La nueva debe cumplir los validadores de Django (min 8 chars, '
            'no muy comun, no similar al username). '
            'NOTA: no invalida otras sesiones activas (DT-S2-03).'
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
            return Response({'message': 'Contrasena actualizada exitosamente.'})
        return Response(serializer.errors, status=400)


# ─── Sprint 3 ─────────────────────────────────────────────────────────
import rest_framework.pagination
from django.contrib.auth import get_user_model
User = get_user_model()

from rest_framework.generics import ListAPIView
from rest_framework.filters import SearchFilter
from django.db.models import Q

from .tokens_email import (
    check_rate_limit, create_password_reset_token, send_password_reset_email,
    validate_password_reset_token, invalidate_all_sessions,
    create_verification_token, send_verification_email, validate_verification_token,
)
from .serializers import (
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    EmailVerificationSerializer, ResendVerificationSerializer,
    AdminUserListSerializer,
)


class PasswordResetRequestView(APIView):
    """POST /api/v1/auth/password-reset/ — UC-AUTH-09 Fase 1."""
    permission_classes = [AllowAny]

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
            pass  # Silencioso — no revela si el email existe

        return Response(
            {'message': 'Si ese email esta registrado, recibiras las instrucciones.'}
        )


class PasswordResetConfirmView(APIView):
    """POST /api/v1/auth/password-reset/confirm/ — UC-AUTH-09 Fase 2."""
    permission_classes = [AllowAny]

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

        from django.utils import timezone
        from django.db import transaction

        with transaction.atomic():
            user = token_obj.user
            user.set_password(serializer.validated_data['new_password'])
            user.save(update_fields=['password'])
            token_obj.used_at = timezone.now()
            token_obj.save(update_fields=['used_at'])
            invalidate_all_sessions(user)

        return Response({'message': 'Contrasena restablecida exitosamente. Inicia sesion.'})


class EmailVerifyView(APIView):
    """POST /api/v1/auth/verify-email/ — UC-AUTH-10."""
    permission_classes = [AllowAny]

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
            return Response({'token': str(e)}, status=400)

        if token_obj is None:
            return Response({'message': 'Tu cuenta ya esta activa. Puedes iniciar sesion.'})

        from django.utils import timezone
        from django.db import transaction

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
            token_obj.save(update_fields=['used_at'])

        return Response({'message': 'Cuenta activada exitosamente. Puedes iniciar sesion.'})


class ResendVerificationView(APIView):
    """POST /api/v1/auth/resend-verification/ — UC-AUTH-10."""
    permission_classes = [AllowAny]

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
                send_verification_email(user, plain)
            # else: silencio deliberado (suspended).
        except User.DoesNotExist:
            pass  # Silencioso

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
    permission_classes = [IsAuthenticated]

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
        serializer = DeactivateAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        user = request.user
        if not user.check_password(serializer.validated_data['password']):
            return Response({'detail': 'Contrasena incorrecta.'}, status=400)

        from django.utils import timezone
        from django.db import transaction
        from .tokens_email import invalidate_all_sessions
        with transaction.atomic():
            user.is_active = False
            user.deactivated_reason = User.DEACTIVATION_SELF_DELETED
            user.deactivated_at = timezone.now()
            user.save(update_fields=[
                'is_active', 'deactivated_reason', 'deactivated_at',
            ])
            invalidate_all_sessions(user)

        return Response({'message': 'Tu cuenta ha sido dada de baja.'}, status=200)


class AdminUserPagination(rest_framework.pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminUserListView(ListAPIView):
    """GET /api/v1/admin/users/ — UC-AUTH-11."""
    permission_classes  = [IsAuthenticated]
    serializer_class    = AdminUserListSerializer
    filter_backends     = [SearchFilter]
    search_fields       = ['username', 'email', 'first_name', 'last_name']
    pagination_class    = AdminUserPagination

    def get_queryset(self):
        if not self.request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo administradores pueden acceder a este endpoint.')
        qs = User.objects.all().order_by('-date_joined')
        is_active = self.request.query_params.get('is_active')
        is_staff  = self.request.query_params.get('is_staff')
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if is_staff is not None:
            qs = qs.filter(is_staff=(is_staff.lower() == 'true'))
        return qs

    @extend_schema(
        summary='Listar usuarios (Admin)',
        description='Listado paginado de todos los usuarios. Solo staff.',
        responses={200: AdminUserListSerializer(many=True)},
        tags=['admin'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
