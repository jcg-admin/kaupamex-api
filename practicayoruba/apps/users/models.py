"""
Models — apps.users (modelo party, DEC-02/03, U-D puro)

IdentityUser: identidad + credenciales, 100% propio (NO hereda
    ``AbstractBaseUser``). Reimplementa a mano el contrato de auth sensible
    (set_password/check_password/get_session_auth_hash) — decisión del ejecutor
    en :ref:`hallazgo-h-api-party-02` (U-D puro). ``email`` es ``USERNAME_FIELD``;
    NO tiene ``username``/``is_staff``/``is_superuser``/``groups`` (superadmin es
    un ``Role`` de ``apps.authz``, DEC-01=B).
Person: atributos humanos del party (nombre, teléfono, avatar) — 1:1 con
    IdentityUser.
CustomerProfile / EmployeeProfile: facetas del party (comprador / empleado).
Address: direcciones de envío (máx 5 por comprador), 1NF, enlazable al catálogo
    internacional ``geo.CatalogPostalCode``.
"""
import os
import time

from django.conf import settings
from django.contrib.auth import hashers
from django.db import models, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from apps.core.logging_context import get_correlation_id
from apps.core.models import AppendOnlyModel, SoftDeleteModel, TimeStampedModel


def avatar_upload_path(instance, filename):
    """Path para avatares subidos. El Sprint 2 convierte a WebP."""
    ext = filename.rsplit('.', 1)[-1].lower()
    ts = int(time.time())
    return os.path.join('avatars', f'person_{instance.pk}_{ts}.{ext}')


# Salt canónico de Django para el HMAC de invalidación de sesión. Se replica
# verbatim para que el comportamiento (cambio de password ⇒ sesión invalidada)
# sea idéntico al de AbstractBaseUser. Ver hallazgo-h-api-party-02.
_SESSION_AUTH_KEY_SALT = (
    'django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash'
)


class IdentityUserManager(models.Manager):
    """Manager del modelo de identidad (reimplementa ``BaseUserManager``).

    U-D puro: no hereda ``BaseUserManager`` para no arrastrar la maquinaria de
    ``AbstractBaseUser``; sólo replica los métodos que el framework y los
    comandos (``createsuperuser``) consumen.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio para IdentityUser')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    @staticmethod
    def normalize_email(email):
        """Normaliza el dominio a minúsculas (copia de BaseUserManager)."""
        email = email or ''
        try:
            email_name, domain_part = email.strip().rsplit('@', 1)
        except ValueError:
            return email.strip()
        return email_name + '@' + domain_part.lower()

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Crea la identidad. El rol ``superadmin`` (DEC-01=B) se asigna aparte
        en el seed de ``apps.authz`` — U-D puro no tiene flag ``is_superuser``.
        """
        extra_fields.setdefault('is_active', True)
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})


class IdentityUser(models.Model):
    """Identidad + credenciales (U-D puro). NO hereda AbstractBaseUser.

    Contrato de auth reimplementado a mano (condición de cierre de T-203, con
    batería de tests de invalidación de sesión — ver hallazgo-h-api-party-02).
    """

    # UC-AUTH-01 Alt-A + UC-AUTH-13/16: causas distintas de is_active=False.
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

    # --- Contrato de identidad (reemplaza AbstractBaseUser) ---
    email = models.EmailField(
        unique=True, db_index=True,
        verbose_name='Correo electrónico',
        help_text='Identificador de login (USERNAME_FIELD).',
    )
    password = models.CharField(max_length=128, verbose_name='Contraseña')
    last_login = models.DateTimeField(
        null=True, blank=True, verbose_name='Último acceso',
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Activo',
        help_text='Cuenta operativa. False = desactivada (ver deactivated_reason).',
    )
    date_joined = models.DateTimeField(
        default=timezone.now, verbose_name='Fecha de alta',
    )
    deactivated_reason = models.CharField(
        max_length=20, choices=DEACTIVATION_REASON_CHOICES,
        null=True, blank=True, verbose_name='Causa de inactividad',
        help_text=(
            'Causa por la que is_active=False. NULL cuando la cuenta está '
            'activa. Distingue cuentas reactivables por email '
            '(unverified, self_deleted) de las que requieren UC-AUTH-14 '
            '(suspended). Ver UC-AUTH-01 Alt-A.'
        ),
    )
    deactivated_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Fecha de desactivación',
    )
    mp_customer_id = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='ID cliente MercadoPago',
        help_text='ID del customer en MP para guardar tarjetas. BR-009.',
    )

    objects = IdentityUserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'
    REQUIRED_FIELDS = []

    # Sentinela de cambio de password (replica AbstractBaseUser._password).
    _password = None

    class Meta:
        db_table = 'users_identity_user'
        verbose_name = 'Identidad de usuario'
        verbose_name_plural = 'Identidades de usuario'

    def __str__(self):
        return self.email

    # --- Contrato de auth (reimplementación manual, U-D puro) ---
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_username(self):
        return getattr(self, self.USERNAME_FIELD)

    def natural_key(self):
        return (self.get_username(),)

    def set_password(self, raw_password):
        self.password = hashers.make_password(raw_password)
        self._password = raw_password

    def check_password(self, raw_password):
        """Verifica el password y re-hashea si el hasher quedó obsoleto."""
        def setter(raw):
            self.set_password(raw)
            # _password evita disparar el señal de cambio en el re-hash.
            self._password = None
            self.save(update_fields=['password'])
        return hashers.check_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        self.password = hashers.make_password(None)

    def has_usable_password(self):
        return hashers.is_password_usable(self.password)

    def get_session_auth_hash(self):
        """HMAC del hash de password. Cambia al cambiar password ⇒ invalida
        sesiones. Idéntico a AbstractBaseUser.get_session_auth_hash."""
        return salted_hmac(
            _SESSION_AUTH_KEY_SALT, self.password, algorithm='sha256',
        ).hexdigest()

    def get_session_auth_fallback_hash(self):
        """Hashes bajo SECRET_KEY_FALLBACKS — mantiene válidas las sesiones
        viejas durante la rotación de SECRET_KEY."""
        for fallback_secret in settings.SECRET_KEY_FALLBACKS:
            yield salted_hmac(
                _SESSION_AUTH_KEY_SALT, self.password,
                secret=fallback_secret, algorithm='sha256',
            ).hexdigest()

    # --- Presentación / party ---
    def get_full_name(self):
        person = getattr(self, 'person', None)
        return person.get_full_name() if person else ''

    def get_short_name(self):
        person = getattr(self, 'person', None)
        return person.first_name if person else ''

    @property
    def first_name(self):
        """Accesor de solo lectura al nombre del ``Person`` (los nombres viven
        en ``Person``, no en la identidad — party DEC-02/03). Presente por
        ergonomía: el contrato de usuario de Django expone ``first_name``."""
        person = getattr(self, 'person', None)
        return person.first_name if person else ''

    @property
    def last_name(self):
        """Accesor de solo lectura al apellido del ``Person`` (ver
        ``first_name``)."""
        person = getattr(self, 'person', None)
        return person.last_name if person else ''

    def profile_completeness(self):
        """Porcentaje de completitud del perfil (FR-AUTH-05.03). Cinco campos,
        20% cada uno. Valores: 0, 20, 40, 60, 80, 100."""
        person = getattr(self, 'person', None)
        score = 0
        if person and person.first_name:
            score += 20
        if person and person.last_name:
            score += 20
        if person and person.phone:
            score += 20
        if person and person.avatar:
            score += 20
        if self.addresses.exists():
            score += 20
        return score

    def pending_fields(self):
        """Campos opcionales del perfil pendientes de completar."""
        person = getattr(self, 'person', None)
        pending = []
        if not (person and person.first_name):
            pending.append('first_name')
        if not (person and person.last_name):
            pending.append('last_name')
        if not (person and person.phone):
            pending.append('phone')
        if not (person and person.avatar):
            pending.append('avatar')
        if not self.addresses.exists():
            pending.append('addresses')
        return pending

    def get_avatar_url(self, request=None):
        """URL absoluta del avatar del Person, o None."""
        person = getattr(self, 'person', None)
        if not person or not person.avatar:
            return None
        try:
            if request:
                return request.build_absolute_uri(person.avatar.url)
            return person.avatar.url
        except (ValueError, AttributeError):
            # silent OK: contrato get_avatar_url() -> None cuando el storage no
            # resuelve la URL (archivo huérfano). DEC-DOC-008.
            return None


class Person(TimeStampedModel):
    """Atributos humanos del party (nombre, contacto, avatar). 1:1 con la
    identidad. Separa el "quién es" (Person) del "cómo entra" (IdentityUser),
    patrón party (DEC-02/03)."""

    identity = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='person', verbose_name='Identidad',
    )
    first_name = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Nombre',
    )
    last_name = models.CharField(
        max_length=150, blank=True, default='', verbose_name='Apellidos',
    )
    phone = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Teléfono',
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_path, null=True, blank=True,
        verbose_name='Avatar',
        help_text='Imagen de perfil. Formatos: JPEG, PNG, WebP.',
    )

    class Meta:
        db_table = 'users_person'
        verbose_name = 'Persona'
        verbose_name_plural = 'Personas'

    def get_full_name(self):
        full = f'{self.first_name} {self.last_name}'.strip()
        return full

    def __str__(self):
        return self.get_full_name() or self.identity.email


class CustomerProfile(TimeStampedModel):
    """Faceta comprador del party (BR-009 y perfil de compra). 1:1 con la
    identidad; presente sólo para identidades que compran."""

    identity = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='customer_profile', verbose_name='Identidad',
    )
    marketing_opt_in = models.BooleanField(
        default=False, verbose_name='Acepta marketing',
    )

    class Meta:
        db_table = 'users_customer_profile'
        verbose_name = 'Perfil de comprador'
        verbose_name_plural = 'Perfiles de comprador'

    def __str__(self):
        return f'CustomerProfile[{self.identity.email}]'


class EmployeeProfile(TimeStampedModel):
    """Faceta empleado del party (staff interno). 1:1 con la identidad;
    presente sólo para identidades del personal. La autorización efectiva la
    resuelve ``apps.authz`` (roles/capacidades), NO este perfil."""

    identity = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='employee_profile', verbose_name='Identidad',
    )
    employee_code = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Código de empleado',
    )

    class Meta:
        db_table = 'users_employee_profile'
        verbose_name = 'Perfil de empleado'
        verbose_name_plural = 'Perfiles de empleado'

    def __str__(self):
        return f'EmployeeProfile[{self.identity.email}]'


class Address(TimeStampedModel, SoftDeleteModel):
    """
    Dirección de envío del comprador (FR-AUTH-07.02, FR-AUTH-07.04).
    Máximo 5 por usuario. Solo una puede ser is_default=True a la vez.

    Hereda SoftDeleteModel (DEC-DOC-007). ``postal_code_ref`` enlaza opcional al
    catálogo internacional ``geo.CatalogPostalCode`` (una colonia concreta); el
    texto libre ``zip_code`` se conserva para retro-compat y direcciones sin
    match en catálogo.
    """
    MAX_PER_USER = 5

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='addresses', verbose_name='Comprador',
    )
    alias = models.CharField(
        max_length=50, verbose_name='Nombre de la dirección',
        help_text='Ej: Casa, Trabajo, Almacén.',
    )
    recipient_name = models.CharField(
        max_length=150, verbose_name='Nombre del destinatario',
    )
    street = models.CharField(max_length=200, verbose_name='Calle y número')
    exterior_number = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Número exterior',
        help_text='Número exterior (MX). Ej: 123, 45-B.',
    )
    interior_number = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Número interior',
        help_text='Número interior si aplica (MX). Ej: Depto 5.',
    )
    neighborhood = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Colonia',
        help_text='Colonia / neighborhood (MX).',
    )
    city = models.CharField(max_length=100, verbose_name='Ciudad')
    state = models.CharField(max_length=100, verbose_name='Estado')
    zip_code = models.CharField(max_length=10, verbose_name='Código postal')
    country = models.CharField(
        max_length=2, default='MX', verbose_name='País',
        help_text='Código ISO 3166-1 alpha-2.',
    )
    postal_code_ref = models.ForeignKey(
        'geo.CatalogPostalCode', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='addresses',
        verbose_name='Código postal (catálogo)',
        help_text='Enlace opcional a la colonia del catálogo internacional.',
    )
    phone = models.CharField(max_length=20, verbose_name='Teléfono del destinatario')
    is_default = models.BooleanField(default=False, verbose_name='Dirección predeterminada')

    class Meta:
        db_table = 'users_address'
        verbose_name = 'Dirección de envío'
        verbose_name_plural = 'Direcciones de envío'
        ordering = ['-is_default', 'alias']

    def __str__(self):
        return f'{self.alias} — {self.user.email}'

    def save(self, *args, **kwargs):
        """Invariante: solo una dirección is_default por usuario (atómica,
        FR-AUTH-07.04)."""
        if self.is_default:
            with transaction.atomic():
                Address.objects.filter(
                    user=self.user, is_default=True,
                ).exclude(pk=self.pk).update(is_default=False, updated_at=timezone.now())
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)


class UserDeactivationEvent(TimeStampedModel):
    """Audit log append-only de transiciones is_active=True -> False (GAP 10)."""
    SOURCE_REGISTER = 'register'
    SOURCE_SELF     = 'self'
    SOURCE_ADMIN    = 'admin'
    SOURCE_CHOICES = [
        (SOURCE_REGISTER, 'Registro (cuenta nueva inactiva por verificar)'),
        (SOURCE_SELF,     'Auto-baja del propio usuario'),
        (SOURCE_ADMIN,    'Suspensión por administrador'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='deactivation_events',
    )
    reason = models.CharField(
        max_length=20, choices=IdentityUser.DEACTIVATION_REASON_CHOICES,
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        help_text=(
            'Quién disparó el evento. NULL para SOURCE_REGISTER o '
            'SOURCE_SELF. Solo SOURCE_ADMIN registra al admin.'
        ),
    )
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'users_deactivation_event'
        verbose_name = 'Evento de desactivación'
        verbose_name_plural = 'Eventos de desactivación'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f'{self.user.email} -> {self.reason} via {self.source}'


class PasswordResetToken(TimeStampedModel):
    """Token de recuperación de contraseña (UC-AUTH-09). Hash-only, 1h, un uso."""
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users_password_reset_token'
        ordering = ['-created_at']

    def __str__(self):
        return f'PasswordReset [{self.user.email}] — usado: {bool(self.used_at)}'


class EmailVerificationToken(TimeStampedModel):
    """Token de verificación de email (UC-AUTH-10). Hash-only, 24h, idempotente."""
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='email_verification_tokens',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'users_email_verification_token'
        ordering = ['-created_at']

    def __str__(self):
        return f'EmailVerif [{self.user.email}] — usado: {bool(self.used_at)}'


class AuthEvent(TimeStampedModel):
    """Audit log de eventos de autenticación (append-only, PII safe)."""
    ACTION_LOGIN_SUCCESS     = "LOGIN_SUCCESS"
    ACTION_LOGIN_FAIL        = "LOGIN_FAIL"
    ACTION_LOGOUT            = "LOGOUT"
    ACTION_REFRESH_SUCCESS   = "REFRESH_SUCCESS"
    ACTION_REFRESH_FAIL      = "REFRESH_FAIL"
    ACTION_REGISTER_ATTEMPT  = "REGISTER_ATTEMPT"
    ACTION_REGISTER_SUCCESS  = "REGISTER_SUCCESS"
    ACTION_REGISTER_FAIL     = "REGISTER_FAIL"
    ACTION_PASSWORD_CHANGE   = "PASSWORD_CHANGE"
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
        (ACTION_PASSWORD_CHANGE,  "Cambio de contraseña"),
        (ACTION_ADDRESS_CREATED,  "Dirección creada"),
        (ACTION_ADDRESS_UPDATED,  "Dirección actualizada"),
        (ACTION_ADDRESS_DELETED,  "Dirección eliminada"),
        (ACTION_ADDRESS_DEFAULT,  "Dirección predeterminada"),
    ]

    REASON_BAD_CREDS          = "BAD_CREDS"
    REASON_ACCOUNT_INACTIVE   = "ACCOUNT_INACTIVE"
    REASON_EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    REASON_RATE_LIMITED       = "RATE_LIMITED"
    REASON_TOKEN_EXPIRED      = "TOKEN_EXPIRED"
    REASON_TOKEN_INVALID      = "TOKEN_INVALID"

    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
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
        u = self.user.email if self.user_id else "anon"
        return f"AuthEvent[{u}] {self.action} {self.created_at:%Y-%m-%d %H:%M}"


class BusinessEvent(AppendOnlyModel):
    """Audit trail de eventos business cross-cutting (append-only, PII safe)."""
    ACTION_ORDER_CREATED          = "ORDER_CREATED"
    ACTION_ORDER_CANCELLED        = "ORDER_CANCELLED"
    ACTION_RETURN_REQUESTED       = "RETURN_REQUESTED"
    ACTION_RETURN_RESOLVED        = "RETURN_RESOLVED"
    ACTION_STOCK_ADJUSTED_TO_ZERO = "STOCK_ADJUSTED_TO_ZERO"
    ACTION_RECEIPT_PDF_GENERATED  = "RECEIPT_PDF_GENERATED"
    ACTION_CHOICES = [
        (ACTION_ORDER_CREATED,          "Order creada"),
        (ACTION_ORDER_CANCELLED,        "Order cancelada"),
        (ACTION_RETURN_REQUESTED,       "Return solicitada"),
        (ACTION_RETURN_RESOLVED,        "Return resuelta"),
        (ACTION_STOCK_ADJUSTED_TO_ZERO, "Stock ajustado a cero"),
        (ACTION_RECEIPT_PDF_GENERATED,  "Receipt PDF generado"),
    ]

    TARGET_ORDER   = "order"
    TARGET_RETURN  = "return"
    TARGET_VARIANT = "variant"
    TARGET_PAYMENT = "payment"

    actor       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="business_events",
    )
    action      = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    target_type = models.CharField(max_length=20, blank=True, default="")
    target_id   = models.PositiveIntegerField(null=True, blank=True)
    ip_addr     = models.GenericIPAddressField(null=True, blank=True)
    extra_json  = models.JSONField(null=True, blank=True)
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
        # llamador no lo fijó explícitamente. No pisa un valor ya provisto.
        if not self.correlation_id:
            self.correlation_id = get_correlation_id() or ""
        super().save(*args, **kwargs)

    def __str__(self):
        a = self.actor.email if self.actor_id else "system"
        return f"BusinessEvent[{a}] {self.action} {self.target_type}#{self.target_id}"


class UserSession(models.Model):
    """UC-AUTH-17 (H-16): registro de sesiones activas del comprador."""
    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="active_sessions",
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
        return f"UserSession[{self.user.email}] {self.session_key[:8]}…"
