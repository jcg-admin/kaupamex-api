"""
Models — apps.users

User: modelo de comprador extendido de AbstractUser.
Address: direcciones de envio del comprador (max 5 por usuario).
"""
import os
import time

from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone
from apps.core.logging_context import get_correlation_id
from apps.core.models import SoftDeleteModel, TimeStampedModel



def avatar_upload_path(instance, filename):
    """Path para avatares subidos. El Sprint 2 convierte a WebP."""
    ext = filename.rsplit('.', 1)[-1].lower()
    ts = int(time.time())
    return os.path.join('avatars', f'user_{instance.pk}_{ts}.{ext}')


class User(AbstractUser):
    # UC-AUTH-01 Alt-A (refinado) + UC-AUTH-13 + UC-AUTH-16:
    # is_active=False puede tener tres causas distintas. El flag
    # solo no las distingue, lo que filtraba E2/E3/E4 al mismo
    # codigo. Estos dos campos las separan para que UC-AUTH-01
    # Alt-A y ResendVerificationView decidan correctamente si la
    # cuenta es reactivable via email.
    DEACTIVATION_UNVERIFIED   = 'unverified'
    DEACTIVATION_SUSPENDED    = 'suspended'
    DEACTIVATION_SELF_DELETED = 'self_deleted'
    DEACTIVATION_REASON_CHOICES = [
        (DEACTIVATION_UNVERIFIED,   'No verificada (email pendiente)'),
        (DEACTIVATION_SUSPENDED,    'Suspendida por administrador'),
        (DEACTIVATION_SELF_DELETED, 'Dada de baja por el usuario'),
    ]
    DEACTIVATION_REASONS_REACTIVABLE_BY_EMAIL = {
        DEACTIVATION_UNVERIFIED,
        DEACTIVATION_SELF_DELETED,
    }

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
    deactivated_reason = models.CharField(
        max_length=20,
        choices=DEACTIVATION_REASON_CHOICES,
        null=True, blank=True,
        verbose_name='Causa de inactividad',
        help_text=(
            'Causa por la que is_active=False. NULL cuando la cuenta esta '
            'activa. Distingue cuentas reactivables por email '
            '(unverified, self_deleted) de las que requieren UC-AUTH-14 '
            '(suspended). Ver UC-AUTH-01 Alt-A.'
        ),
    )
    deactivated_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha de desactivacion',
        help_text='Timestamp del cambio is_active True -> False.',
    )
    mp_customer_id = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='ID cliente MercadoPago',
        help_text='ID del customer en MP para guardar tarjetas. BR-009.',
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
            # silent OK because contract: get_avatar_url() retorna None
            # cuando el storage no puede resolver la URL (archivo
            # huerfano). DEC-DOC-008.
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


class Address(TimeStampedModel, SoftDeleteModel):
    """
    Direccion de envio del comprador (FR-AUTH-07.02, FR-AUTH-07.04).
    Maximo 5 por usuario. Solo una puede ser is_default=True a la vez.

    Hereda SoftDeleteModel (DEC-DOC-007): un Address borrado conserva
    la referencia historica desde Order/Shipment (snapshot ya esta en
    OrderAddress, pero preservar la fila original facilita auditoria
    y trazabilidad).
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
    # DEC-AUM-03 (UC-AUTH-07 D-01-07): direcciones MX requieren
    # numero exterior / interior / colonia segun convencion postal.
    # Backwards-compat: blank=True para no romper rows previos.
    exterior_number = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Numero exterior',
        help_text='Numero exterior (MX). Ej: 123, 45-B.',
    )
    interior_number = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Numero interior',
        help_text='Numero interior si aplica (MX). Ej: Depto 5.',
    )
    neighborhood = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Colonia',
        help_text='Colonia / neighborhood (MX).',
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
                ).exclude(pk=self.pk).update(is_default=False, updated_at=timezone.now())
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class UserDeactivationEvent(TimeStampedModel):
    """
    Audit log de transiciones is_active=True -> False (GAP 10 cierre).

    Cierra el gap de observabilidad detectado en el audit profundo:
    el flag users_user.is_active + deactivated_reason refleja el ESTADO
    actual, pero no preserva el historial. Si la cuenta se reactiva y
    despues se vuelve a dar de baja por otro motivo, perdemos la pista
    del evento anterior.

    Esta tabla append-only registra cada transicion:

    - user: a quien afecta.
    - reason: que motivo se aplico ('unverified', 'suspended', 'self_deleted').
    - actor: quien la inicio. NULL si fue el propio usuario o un signal
      (created_with_is_active_false en RegisterSerializer). Otro user
      cuando UC-AUTH-13 (admin suspend).
    - source: que codepath la genero ('register', 'self', 'admin').
    - note: texto libre opcional para el admin.

    Las reactivaciones (is_active=False -> True) NO se registran aqui —
    el evento de cierre se infiere por la fecha del siguiente evento o
    por users_user.deactivated_reason IS NULL.
    """
    SOURCE_REGISTER = 'register'
    SOURCE_SELF     = 'self'
    SOURCE_ADMIN    = 'admin'
    SOURCE_CHOICES = [
        (SOURCE_REGISTER, 'Registro (cuenta nueva inactiva por verificar)'),
        (SOURCE_SELF,     'Auto-baja del propio usuario'),
        (SOURCE_ADMIN,    'Suspension por administrador'),
    ]

    user = models.ForeignKey(
        'users.User', on_delete=models.CASCADE,
        related_name='deactivation_events',
    )
    reason = models.CharField(
        max_length=20,
        choices=User.DEACTIVATION_REASON_CHOICES,
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    actor = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text=(
            'Quien disparo el evento. NULL para SOURCE_REGISTER o '
            'SOURCE_SELF. Solo SOURCE_ADMIN registra al admin.'
        ),
    )
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'users_deactivation_event'
        verbose_name = 'Evento de desactivacion'
        verbose_name_plural = 'Eventos de desactivacion'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f'{self.user.username} -> {self.reason} via {self.source}'


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


class AuthEvent(TimeStampedModel):
    """
    Audit log de eventos de autenticacion (UC-AUTH-02/03/04
    POST-05/AC-06, audit T-102 D-09/D-10/D-19/D-25).

    Append-only. PII safe: NO almacena passwords ni tokens.
    Solo registra: user FK (nullable para login_fail con
    user inexistente), action enum (EN canonico), ip, ua,
    reason enum, extra_json para correlation_id u otros
    contextos.

    Ver iniciativa audit-log-eventos-auth (DEC-AL-1..6).
    """
    ACTION_LOGIN_SUCCESS     = "LOGIN_SUCCESS"
    ACTION_LOGIN_FAIL        = "LOGIN_FAIL"
    ACTION_LOGOUT            = "LOGOUT"
    ACTION_REFRESH_SUCCESS   = "REFRESH_SUCCESS"
    ACTION_REFRESH_FAIL      = "REFRESH_FAIL"
    # audit-log-eventos-auth-register (DEC-ALR-1):
    ACTION_REGISTER_ATTEMPT  = "REGISTER_ATTEMPT"
    ACTION_REGISTER_SUCCESS  = "REGISTER_SUCCESS"
    ACTION_REGISTER_FAIL     = "REGISTER_FAIL"
    # T-119 D-02 iter 20 (UC-AUTH-08 AC-06 audit log universal):
    ACTION_PASSWORD_CHANGE   = "PASSWORD_CHANGE"
    # D-04-07 (hardening-addresses): audit log CRUD + set-default.
    ACTION_ADDRESS_CREATED   = "ADDRESS_CREATED"
    ACTION_ADDRESS_UPDATED   = "ADDRESS_UPDATED"
    ACTION_ADDRESS_DELETED   = "ADDRESS_DELETED"
    ACTION_ADDRESS_DEFAULT   = "ADDRESS_DEFAULT"
    ACTION_CHOICES = [
        (ACTION_LOGIN_SUCCESS,    "Login exitoso"),
        (ACTION_LOGIN_FAIL,       "Login fallido"),
        (ACTION_LOGOUT,           "Logout"),
        (ACTION_REFRESH_SUCCESS,  "Refresh exitoso"),
        (ACTION_REFRESH_FAIL,     "Refresh fallido"),
        (ACTION_REGISTER_ATTEMPT, "Registro intento"),
        (ACTION_REGISTER_SUCCESS, "Registro exitoso"),
        (ACTION_REGISTER_FAIL,    "Registro fallido"),
        (ACTION_PASSWORD_CHANGE,  "Cambio de contrasena"),
        (ACTION_ADDRESS_CREATED,  "Direccion creada"),
        (ACTION_ADDRESS_UPDATED,  "Direccion actualizada"),
        (ACTION_ADDRESS_DELETED,  "Direccion eliminada"),
        (ACTION_ADDRESS_DEFAULT,  "Direccion predeterminada"),
    ]

    REASON_BAD_CREDS        = "BAD_CREDS"
    REASON_ACCOUNT_INACTIVE = "ACCOUNT_INACTIVE"
    REASON_EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    REASON_RATE_LIMITED     = "RATE_LIMITED"
    REASON_TOKEN_EXPIRED    = "TOKEN_EXPIRED"
    REASON_TOKEN_INVALID    = "TOKEN_INVALID"

    user       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="auth_events",
    )
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    ip_addr    = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    reason     = models.CharField(max_length=30, blank=True, default="")
    extra_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "users_auth_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "action", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        u = self.user.username if self.user_id else "anon"
        return f"AuthEvent[{u}] {self.action} {self.created_at:%Y-%m-%d %H:%M}"



class BusinessEvent(TimeStampedModel):
    """
    Audit trail de eventos business cross-cutting (orders,
    returns) — distinto de AuthEvent (auth flow). Sucesora
    de audit-log-eventos-auth.

    Patron similar: append-only, PII safe, indexed for
    forensics. target_type + target_id en lugar de
    GenericForeignKey por simplicidad (DEC-CC-4).
    """
    ACTION_ORDER_CREATED          = "ORDER_CREATED"
    ACTION_ORDER_CANCELLED        = "ORDER_CANCELLED"
    ACTION_RETURN_REQUESTED       = "RETURN_REQUESTED"
    ACTION_RETURN_RESOLVED        = "RETURN_RESOLVED"
    ACTION_STOCK_ADJUSTED_TO_ZERO = "STOCK_ADJUSTED_TO_ZERO"
    ACTION_RECIBO_PDF_GENERADO    = "RECIBO_PDF_GENERADO"
    ACTION_CHOICES = [
        (ACTION_ORDER_CREATED,          "Order creada"),
        (ACTION_ORDER_CANCELLED,        "Order cancelada"),
        (ACTION_RETURN_REQUESTED,       "Return solicitada"),
        (ACTION_RETURN_RESOLVED,        "Return resuelta"),
        (ACTION_STOCK_ADJUSTED_TO_ZERO, "Stock ajustado a cero"),
        (ACTION_RECIBO_PDF_GENERADO,    "Recibo PDF generado"),
    ]

    TARGET_ORDER   = "order"
    TARGET_RETURN  = "return"
    TARGET_VARIANT = "variant"
    TARGET_PAYMENT = "payment"

    actor       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="business_events",
    )
    action      = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    target_type = models.CharField(max_length=20, blank=True, default="")
    target_id   = models.PositiveIntegerField(null=True, blank=True)
    ip_addr     = models.GenericIPAddressField(null=True, blank=True)
    extra_json  = models.JSONField(null=True, blank=True)
    # SOL-011 (DEC-LOG-07): une este evento de negocio con RequestLog / AppLog de
    # la misma request. Se autopopula desde el contexto de logging en save(); es
    # vacio para eventos emitidos fuera de un request (management commands, cron).
    correlation_id = models.CharField(max_length=32, db_index=True, blank=True, default="")

    class Meta:
        db_table = "users_business_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def save(self, *args, **kwargs):
        # DEC-LOG-07: sella el correlation_id de la request en curso si el
        # llamador no lo fijo explicitamente. No pisa un valor ya provisto.
        if not self.correlation_id:
            self.correlation_id = get_correlation_id() or ""
        super().save(*args, **kwargs)

    def __str__(self):
        a = self.actor.username if self.actor_id else "system"
        return f"BusinessEvent[{a}] {self.action} {self.target_type}#{self.target_id}"


class UserSession(models.Model):
    """UC-AUTH-17 (H-16): registro de sesiones activas del comprador.

    El SPA usa sesion de servidor (cookie ``sessionid``, ``django_session``);
    Django no guarda IP ni dispositivo por sesion. Este modelo augmenta cada
    sesion con esa metadata (poblado tras ``django_login``) para poder
    listarlas y cerrarlas por dispositivo. ``session_key`` enlaza con la fila
    de ``django_session``; al revocar se borra esa fila (invalida la sesion).
    """
    user          = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="active_sessions",
    )
    session_key   = models.CharField(max_length=40, unique=True, db_index=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.CharField(max_length=400, blank=True, default="")
    created_at    = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users_user_session"
        ordering = ["-last_activity"]
        indexes = [models.Index(fields=["user", "-last_activity"])]

    def __str__(self):
        return f"UserSession[{self.user.username}] {self.session_key[:8]}…"
