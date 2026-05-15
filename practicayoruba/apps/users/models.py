"""
Models — apps.users

User: modelo de comprador extendido de AbstractUser.
Address: direcciones de envio del comprador (max 5 por usuario).
"""
import os
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction

from apps.core.models import TimeStampedModel


def avatar_upload_path(instance, filename):
    """Path para avatares subidos. El Sprint 2 convierte a WebP."""
    import time
    ext = filename.rsplit('.', 1)[-1].lower()
    ts = int(time.time())
    return os.path.join('avatars', f'user_{instance.pk}_{ts}.{ext}')


class User(AbstractUser):
    avatar = models.ImageField(
        upload_to=avatar_upload_path,
        null=True, blank=True,
        verbose_name='Avatar',
        help_text='Imagen de perfil del comprador. Formatos: JPEG, PNG, WebP.',
    )
    phone = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Telefono',
        help_text='Numero de telefono del comprador.',
    )

    class Meta:
        db_table = 'users_user'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.get_full_name() or self.username

    def get_avatar_url(self, request=None):
        """Retorna URL absoluta del avatar o None si no tiene."""
        if not self.avatar:
            return None
        try:
            if request:
                return request.build_absolute_uri(self.avatar.url)
            return self.avatar.url
        except (ValueError, AttributeError):
            return None

    def profile_completeness(self):
        """
        Calcula el porcentaje de completitud del perfil (FR-AUTH-05.03).
        Cinco campos opcionales, 20% cada uno.
        Valores posibles: 0, 20, 40, 60, 80, 100.
        """
        score = 0
        if self.first_name:
            score += 20
        if self.last_name:
            score += 20
        if self.phone:
            score += 20
        if self.avatar:
            score += 20
        if self.addresses.exists():
            score += 20
        return score

    def pending_fields(self):
        """Lista de campos opcionales del perfil pendientes de completar."""
        pending = []
        if not self.first_name:
            pending.append('first_name')
        if not self.last_name:
            pending.append('last_name')
        if not self.phone:
            pending.append('phone')
        if not self.avatar:
            pending.append('avatar')
        if not self.addresses.exists():
            pending.append('addresses')
        return pending


class Address(TimeStampedModel):
    """
    Direccion de envio del comprador (FR-AUTH-07.02, FR-AUTH-07.04).
    Maximo 5 por usuario. Solo una puede ser is_default=True a la vez.
    """
    MAX_PER_USER = 5

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name='Comprador',
    )
    alias = models.CharField(
        max_length=50,
        verbose_name='Nombre de la direccion',
        help_text='Ej: Casa, Trabajo, Almacen.',
    )
    recipient_name = models.CharField(
        max_length=150,
        verbose_name='Nombre del destinatario',
    )
    street = models.CharField(
        max_length=200,
        verbose_name='Calle y numero',
    )
    city = models.CharField(max_length=100, verbose_name='Ciudad')
    state = models.CharField(max_length=100, verbose_name='Estado')
    zip_code = models.CharField(max_length=10, verbose_name='Codigo postal')
    country = models.CharField(
        max_length=2, default='MX',
        verbose_name='Pais',
        help_text='Codigo ISO 3166-1 alpha-2.',
    )
    phone = models.CharField(max_length=20, verbose_name='Telefono del destinatario')
    is_default = models.BooleanField(
        default=False,
        verbose_name='Direccion predeterminada',
    )

    class Meta:
        db_table = 'users_address'
        verbose_name = 'Direccion de envio'
        verbose_name_plural = 'Direcciones de envio'
        ordering = ['-is_default', 'alias']

    def __str__(self):
        return f'{self.alias} — {self.user.username}'

    def save(self, *args, **kwargs):
        """
        Garantiza la invariante: solo una direccion es_default por usuario.
        Si esta direccion se marca como default, las demas se desmarcan.
        Transaccion atomica (FR-AUTH-07.04).
        """
        if self.is_default:
            with transaction.atomic():
                Address.objects.filter(
                    user=self.user, is_default=True
                ).exclude(pk=self.pk).update(is_default=False)
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class PasswordResetToken(TimeStampedModel):
    """
    Token de recuperacion de contrasena (UC-AUTH-09, FR-AUTH-09.03).
    El token en claro se envia al email. Solo el hash se guarda en BD.
    Validez: 1 hora. Un solo uso.
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='password_reset_tokens')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users_password_reset_token'
        ordering = ['-created_at']

    def __str__(self):
        return f'PasswordReset [{self.user.username}] — usado: {bool(self.used_at)}'


class EmailVerificationToken(TimeStampedModel):
    """
    Token de verificacion de email (UC-AUTH-10, FR-AUTH-10.02).
    El token en claro se envia al email. Solo el hash se guarda en BD.
    Validez: 24 horas. Idempotente si la cuenta ya esta activa.
    """
    user       = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='email_verification_tokens')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users_email_verification_token'
        ordering = ['-created_at']

    def __str__(self):
        return f'EmailVerif [{self.user.username}] — usado: {bool(self.used_at)}'
