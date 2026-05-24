"""
Serializers — apps.users

Sprint 1: RegisterSerializer
Sprint 2: ProfileSerializer, UpdateProfileSerializer,
          ChangePasswordSerializer, AddressSerializer
"""
import io
import logging
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from PIL import Image
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from apps.settings_app.models import SiteSettings
from .audit import audit_log_auth
from .models import Address, AuthEvent, UserDeactivationEvent
from .tokens_email import invalidate_all_sessions
from .tokens_email import create_verification_token, send_verification_email

logger = logging.getLogger(__name__)





User = get_user_model()

AMBIGUOUS_MSG = 'Los datos ingresados no estan disponibles. Prueba con otros.'

# ─── Sprint 1 ───────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    """
    UC-AUTH-01: Registro de comprador.
    FR-AUTH-01.02: validar formato
    FR-AUTH-01.03: unicidad con mensaje ambiguo
    FR-AUTH-01.04: is_active=False

    Request: { first_name, last_name, email, password, password_confirm,
               terms_accepted }
    El username se auto-genera del email (email[:150]).
    """
    first_name       = serializers.CharField(max_length=150, required=False, default='', allow_blank=True)
    last_name        = serializers.CharField(max_length=150, required=False, default='', allow_blank=True)
    email            = serializers.EmailField()
    password         = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    terms_accepted   = serializers.BooleanField()

    def validate_email(self, value):
        # UC-AUTH-01 refinado: la deteccion de email existente vive en
        # RegisterView.post para que pueda discriminar por
        # deactivated_reason (Alt-A.1/A.2/A.3). Aqui solo se normaliza.
        return value.lower().strip()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_terms_accepted(self, value):
        if not value:
            raise serializers.ValidationError(
                'Debes aceptar los terminos y condiciones para registrarte.'
            )
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Las contrasenas no coinciden.'}
            )
        return attrs

    @staticmethod
    def _generate_username(email: str) -> str:
        base = email[:150]
        if not User.objects.filter(username__iexact=base).exists():
            return base
        i = 1
        while True:
            candidate = f"{email[:147]}_{i}"
            if not User.objects.filter(username__iexact=candidate).exists():
                return candidate
            i += 1

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data.pop('terms_accepted', None)
        first_name = validated_data.pop('first_name', '')
        last_name  = validated_data.pop('last_name', '')
        email      = validated_data['email']
        username   = self._generate_username(email)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data['password'],
            first_name=first_name,
            last_name=last_name,
            is_active=False,
        )
        user.deactivated_reason = User.DEACTIVATION_UNVERIFIED
        user.deactivated_at = timezone.now()
        user.save(update_fields=['deactivated_reason', 'deactivated_at'])
        UserDeactivationEvent.objects.create(
            user=user,
            reason=User.DEACTIVATION_UNVERIFIED,
            source=UserDeactivationEvent.SOURCE_REGISTER,
            actor=None,
        )
        user_id = user.pk

        def _send_verification():
            try:
                u = User.objects.get(pk=user_id)
                plain = create_verification_token(u)
                send_verification_email(u, plain)
            except User.DoesNotExist:
                logger.info(
                    'verification email skipped: user_id=%s removed '
                    'before on_commit', user_id,
                )

        transaction.on_commit(_send_verification)
        return user


# ─── Sprint 2 ───────────────────────────────────────────────────────

class AddressSerializer(serializers.ModelSerializer):
    """UC-AUTH-07: Serializer de direccion de envio."""

    class Meta:
        model = Address
        fields = [
            'id', 'alias', 'recipient_name', 'street',
            'exterior_number', 'interior_number', 'neighborhood',
            'city', 'state', 'zip_code', 'country',
            'phone', 'is_default',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        if user and not self.instance:
            max_addr = Address.MAX_PER_USER
            count = Address.objects.filter(user=user).count()
            if count >= max_addr:
                raise serializers.ValidationError(
                    {'non_field_errors': f'Maximo {max_addr} direcciones por usuario.'},
                    code='limite_direcciones',
                )
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        is_default = validated_data.get('is_default', False)
        is_first = not Address.objects.filter(user=user).exists()
        addr = Address(**validated_data, user=user)
        if is_first or is_default:
            addr.is_default = True
        addr.save()
        return addr


class ProfileSerializer(serializers.ModelSerializer):
    """UC-AUTH-05: Retorna el perfil del comprador autenticado."""
    avatar_url          = serializers.SerializerMethodField()
    profile_completeness = serializers.SerializerMethodField()
    pending_fields      = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email',
            'first_name', 'last_name', 'phone',
            'avatar_url', 'date_joined',
            'profile_completeness', 'pending_fields',
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.URI)
    def get_avatar_url(self, obj):
        request = self.context.get('request')
        return obj.get_avatar_url(request)

    @extend_schema_field(OpenApiTypes.INT)
    def get_profile_completeness(self, obj):
        return obj.profile_completeness()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_pending_fields(self, obj):
        return obj.pending_fields()


ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'JPEG', 'PNG', 'WEBP'}

class UpdateProfileSerializer(serializers.ModelSerializer):
    """UC-AUTH-06: Actualiza campos de perfil. Email y username no editables."""
    remove_avatar = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'avatar', 'remove_avatar']
        extra_kwargs = {
            'avatar': {'required': False, 'allow_null': True},
        }

    def validate_avatar(self, value):
        if value is None:
            return value
        max_mb = 5
        if value.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"El avatar no puede superar {max_mb} MB."
            )
        try:
            img = Image.open(value)
            img.verify()
        except Exception:
            raise serializers.ValidationError(
                'El archivo no es una imagen valida. Usa JPEG, PNG o WebP.'
            )
        value.seek(0)
        img = Image.open(value)
        if img.format not in ('JPEG', 'PNG', 'WEBP'):
            raise serializers.ValidationError(
                'Formato no permitido. Usa JPEG, PNG o WebP.'
            )
        value.seek(0)
        return value

    def update(self, instance, validated_data):
        remove = validated_data.pop('remove_avatar', False)
        avatar_file = validated_data.pop('avatar', None)

        if remove and instance.avatar:
            instance.avatar.delete(save=False)
            instance.avatar = None

        elif avatar_file is not None:
            img = Image.open(avatar_file)
            img.thumbnail((800, 800), Image.LANCZOS)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=85)
            buf.seek(0)

            ts = int(time.time())
            filename = f'user_{instance.pk}_{ts}.webp'

            if instance.avatar:
                instance.avatar.delete(save=False)

            instance.avatar.save(filename, ContentFile(buf.read()), save=False)

        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """UC-AUTH-08: Cambiar contrasena del comprador autenticado."""
    current_password     = serializers.CharField(write_only=True)
    new_password         = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('La contrasena actual es incorrecta.')
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {'new_password_confirm': 'Las contrasenas no coinciden.'}
            )
        if attrs['new_password'] == attrs['current_password']:
            raise serializers.ValidationError(
                'La nueva contrasena debe ser diferente a la actual.'
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        request = self.context['request']
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        invalidate_all_sessions(user)
        audit_log_auth(user, AuthEvent.ACTION_PASSWORD_CHANGE, request)
        return user


# ─── Sprint 3 ───────────────────────────────────────────────────────

class PasswordResetRequestSerializer(serializers.Serializer):
    """UC-AUTH-09 Fase 1: solicitar recuperacion de contrasena."""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """UC-AUTH-09 Fase 2: confirmar token y establecer nueva contrasena."""
    token                = serializers.CharField(write_only=True)
    new_password         = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {'new_password_confirm': 'Las contrasenas no coinciden.'}
            )
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """UC-AUTH-10: verificar email con token del enlace."""
    token = serializers.CharField()


class ResendVerificationSerializer(serializers.Serializer):
    """UC-AUTH-10: reenviar email de verificacion."""
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class AdminUserListSerializer(serializers.ModelSerializer):
    """UC-AUTH-11: datos del usuario para el listado del admin."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'full_name',
            'is_active', 'is_staff', 'date_joined', 'last_login',
            'deactivated_reason', 'deactivated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_full_name(self, obj):
        return obj.get_full_name()
