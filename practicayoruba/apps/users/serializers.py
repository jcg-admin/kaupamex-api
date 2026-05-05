"""
Serializers — apps.users

Sprint 1: RegisterSerializer
Sprint 2: ProfileSerializer, UpdateProfileSerializer,
          ChangePasswordSerializer, AddressSerializer
"""
import io
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from PIL import Image

from .models import Address

User = get_user_model()

AMBIGUOUS_MSG = 'Los datos ingresados no estan disponibles. Prueba con otros.'

# ─── Sprint 1 ─────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    """
    UC-AUTH-01: Registro de comprador.
    FR-AUTH-01.02: validar formato
    FR-AUTH-01.03: unicidad con mensaje ambiguo
    FR-AUTH-01.04: is_active=False
    """
    username         = serializers.CharField(min_length=3, max_length=150)
    email            = serializers.EmailField()
    password         = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(AMBIGUOUS_MSG)
        return value

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(AMBIGUOUS_MSG)
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Las contrasenas no coinciden.'}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False,
        )
        return user


# ─── Sprint 2 ─────────────────────────────────────────────────────────

class AddressSerializer(serializers.ModelSerializer):
    """UC-AUTH-07: Serializer de direccion de envio."""

    class Meta:
        model = Address
        fields = [
            'id', 'alias', 'recipient_name', 'street',
            'city', 'state', 'zip_code', 'country',
            'phone', 'is_default',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user if request else None
        if user and not self.instance:
            count = Address.objects.filter(user=user).count()
            if count >= Address.MAX_PER_USER:
                raise serializers.ValidationError(
                    {'non_field_errors': f'Maximo {Address.MAX_PER_USER} direcciones por usuario.'},
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

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        return obj.get_avatar_url(request)

    def get_profile_completeness(self, obj):
        return obj.profile_completeness()

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
        """
        FR-AUTH-06.04: valida formato y contenido del avatar.
        Intenta abrir con Pillow para detectar archivos falsos.
        """
        if value is None:
            return value
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
            import time
            from django.core.files.base import ContentFile

            img = Image.open(avatar_file)
            # Redimensionar si supera 800x800 (FR-AUTH-06.04)
            img.thumbnail((800, 800), Image.LANCZOS)
            # Convertir a RGB (WebP no soporta RGBA en algunos casos)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='WEBP', quality=85)
            buf.seek(0)

            ts = int(time.time())
            filename = f'user_{instance.pk}_{ts}.webp'

            # Eliminar avatar anterior
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
                {'new_password': 'La nueva contrasena debe ser diferente a la actual.'}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
