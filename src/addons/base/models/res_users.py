"""``res.users`` — la credencial de acceso (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**La decisión que estructura este archivo** es la línea 165 de la referencia::

    _inherits = {'res.partner': 'partner_id'}

``res.users`` **no es la persona**. Es la credencial, y delega quién eres a un
``res.partner`` requerido. Por eso ``name``/``email``/``phone`` figuran en
``res.users`` como campos ``related`` (``:252-255``): se leen del partner, no
se guardan dos veces. Un empleado que deja de tener login sigue existiendo como
partner; un cliente sin cuenta nunca necesita uno.

**Django sí tiene un mecanismo parecido, y no se usa.** La herencia multi-tabla
(MTI) hace mecánicamente casi lo mismo: al heredar de un modelo concreto,
``ModelBase`` inyecta un enlace oculto —``base.py:301-307``,
``OneToOneField(base, on_delete=CASCADE, auto_created=True, parent_link=True)``
llamado ``<modelo>_ptr``— guarda cada tabla por separado y hace el ``JOIN``
implícito. Sería ``class ResUsers(ResPartner)`` y ``name``/``email`` saldrían
gratis, sin las propiedades de abajo.

**Una sola diferencia estructural lo descarta**, y sólo queda en pie porque se
midió: el enlace de MTI es **siempre** ``OneToOneField`` —``parent_link=True``
lo exige—, mientras que ``partner_id`` de la referencia es ``Many2one`` sin
restricción única (``res_users.py:214``). Dos credenciales sobre un mismo
partner: la FK lo permite, MTI da ``IntegrityError``. Declarar el enlace a mano
no lo cambia; sigue siendo ``unique=True``.

Las otras dos objeciones que se escribieron aquí **eran falsas** y se corrigen
(medido con ``parent_link`` declarado explícitamente):

- *"MTI cablea* ``CASCADE`` *y no es configurable"* — **falso**. Declarando el
  campo (``OneToOneField(Parent, on_delete=PROTECT, parent_link=True,
  primary_key=True)``) el ``on_delete`` es el que se elija: borrar el padre da
  ``ProtectedError``. El ``CASCADE`` es sólo el default del campo
  ``auto_created``.
- *"con MTI no se puede adjuntar a un padre preexistente"* — **falso** con ese
  mismo override: ``Child.objects.create(parent_link=<padre existente>, …)``
  **no** crea fila nueva de padre. Lo que no funciona es la vía automática.

Queda además la divergencia conceptual: MTI es *is-a*
(``isinstance(user, ResPartner)`` sería ``True``), mientras que el ORM de la
referencia describe ``_inherits`` como *"implements **composition-based**
inheritance: the new model exposes all the fields of the inherited models but
**stores none of them**"* (``odoo/orm/models.py:416-418``).

Y un argumento de coste, no de capacidad: para que MTI se comportara como la
referencia habría que declarar el ``parent_link`` a mano — momento en que ya se
está escribiendo la FK, sin la automagia que hacía atractivo a MTI, y **aun
así** con la cardinalidad equivocada. Por eso: FK requerida + propiedades que
reenvían.

**Lo que NO se hereda de Django.** El modelo no extiende ``AbstractBaseUser``:
reimplementa el contrato de auth a mano (U-D puro, T-203) para no arrastrar
``is_staff``/``is_superuser`` ni el M2M de permisos nativo — la autorización
vive en ``authz`` por capacidad (DEC-11), y un flag de superusuario saltaría
ese modelo. Los *hashers* de Django sí se usan, como librería.
"""
import fields
import models

from django.apps import apps
from django.conf import settings
from django.contrib.auth import hashers
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import salted_hmac

from addons.base.models.timestamped_mixin import TimeStampedModel

# Sal del HMAC de sesión. Literal de Django (``AbstractBaseUser``): cambiarlo
# invalidaría toda sesión viva, así que se replica verbatim.
_SESSION_AUTH_KEY_SALT = (
    'django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash'
)


class ResUsersManager(models.Manager):
    """Manager de la credencial. Replica lo que el framework consume.

    No hereda ``BaseUserManager`` por la misma razón que el modelo no hereda
    ``AbstractBaseUser``: sólo se replican los métodos que Django y
    ``createsuperuser`` llaman de verdad.
    """

    use_in_migrations = True

    @staticmethod
    def normalize_email(email):
        """Normaliza el dominio a minúsculas (copia de ``BaseUserManager``)."""
        email = email or ''
        try:
            email_name, domain_part = email.strip().rsplit('@', 1)
        except ValueError:
            return email.strip()
        return email_name + '@' + domain_part.lower()

    def _create_user(self, login, password, partner=None, **extra_fields):
        if not login:
            raise ValueError('El login es obligatorio para ResUsers')
        login = self.normalize_email(login)
        if partner is None:
            # La referencia exige ``partner_id``: no hay credencial sin party.
            # Si el llamador no trae uno, se crea el mínimo viable con el
            # login como nombre — igual que ``res.users.create`` de Odoo, que
            # crea el partner cuando falta.
            partner = _partner_model().objects.create(
                name=extra_fields.pop('name', '') or login,
                email=login,
            )
        user = self.model(login=login, partner=partner, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, login, password=None, **extra_fields):
        extra_fields.setdefault('active', True)
        return self._create_user(login, password, **extra_fields)

    def create_superuser(self, login, password=None, **extra_fields):
        """Crea la credencial. El rol ``superadmin`` (DEC-01=B) se asigna en el
        seed de ``authz``: U-D puro no tiene flag ``is_superuser``.
        """
        extra_fields.setdefault('active', True)
        return self._create_user(login, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: username})


def _partner_model():
    """Resuelve ``ResPartner`` por el registro de apps.

    Lo que se difiere es la **resolución** (``get_model``), no el import: un
    import de ``res_partner`` a nivel de módulo cerraría el ciclo
    ``res_users`` → ``res_partner`` → ``__init__``, pero ``django.apps`` es el
    registro, no el modelo, y se importa arriba sin tocar ese ciclo.

    La versión anterior tenía el ``from django.apps import apps`` **dentro** de
    la función y un docstring que lo justificaba como "una llamada, no un
    statement". Era falso —es un statement de import— y sólo pasaba el gate
    porque el gate no miraba este árbol (ver H-API-221).
    """
    return apps.get_model('base', 'ResPartner')


class ResUsers(TimeStampedModel):
    """``res.users`` — credencial de acceso, delegando identidad al partner.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users.py:163-257`` en lo
    estructural: ``partner`` requerido (``partner_id``), ``login``,
    ``password``, ``active``, ``company``. Los campos computados de la
    referencia (``share``, ``companies_count``, ``tz_offset``) no se portan.

    **El M2M a ``res.groups`` sí existe desde ``res_groups.py``.** La nota
    anterior decía que no se portaba; quedó obsoleta al portar ese archivo. La
    referencia declara ``user_ids`` **del lado de ``res.groups``**
    (``res_groups_users_rel``), así que aquí el reverso llega por
    ``related_name='group_ids'`` sin declarar nada. Que exista la relación NO
    cambia la autorización: este árbol sigue autorizando por **capacidad**
    (DEC-11, ``HasCapability`` fail-closed) sobre ``authz``; el re-apuntado de
    los consumidores es una decisión de producto aparte.
    """

    # Causas distintas de ``active=False`` (UC-AUTH-01 Alt-A, UC-AUTH-13/16).
    # No están en la referencia: allí ``active`` es un booleano sin motivo.
    # Se conservan porque el flujo de reactivación por email depende de
    # distinguir "no verificada" de "suspendida por un administrador".
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

    partner       = fields.Many2one(
        'base.ResPartner', on_delete=models.PROTECT, related_name='users',
        help_text=(
            'Party al que pertenece esta credencial (Odoo partner_id). '
            'Requerido: en la referencia no hay usuario sin partner.'
        ),
    )
    login         = fields.Char(
        max_length=254, unique=True, db_index=True,
        help_text='Identificador de acceso (Odoo login). Aquí es el email.',
    )
    password      = fields.Char(max_length=128, verbose_name='Contraseña')
    active        = fields.Boolean(
        default=True, db_index=True,
        help_text='Cuenta operativa (Odoo active).',
    )
    last_login    = fields.Datetime(null=True, blank=True)

    deactivated_reason = fields.Selection(
        max_length=20, choices=DEACTIVATION_REASON_CHOICES,
        null=True, blank=True,
        help_text=(
            'Causa por la que active=False; NULL cuando la cuenta está activa. '
            'Distingue las reactivables por email de las que exigen UC-AUTH-14.'
        ),
    )
    deactivated_at = fields.Datetime(null=True, blank=True)

    company       = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, null=True, blank=True,
        related_name='users',
        help_text=(
            'Company L1 del usuario (Odoo company_id). NULL = operador de '
            'plataforma L0 o sin asignar. Lo consume el resolver de company.'
        ),
    )

    objects = ResUsersManager()

    USERNAME_FIELD = 'login'
    EMAIL_FIELD    = 'login'
    REQUIRED_FIELDS = []

    # Sentinela de cambio de password (replica ``AbstractBaseUser._password``).
    _password = None

    class Meta:
        db_table            = 'res_users'
        ordering            = ['login']
        verbose_name        = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self) -> str:
        return self.login

    # --- Delegación al partner (el ``_inherits`` que Django no tiene) ---
    @property
    def name(self):
        return self.partner.name

    @property
    def email(self):
        """La referencia relaciona ``email`` al del partner (``:253``)."""
        return self.partner.email or self.login

    @property
    def phone(self):
        return self.partner.phone

    # --- Contrato de auth (reimplementación manual, U-D puro) ---
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        """Alias del contrato de Django sobre el ``active`` de la referencia.

        Django consulta ``is_active`` en ``ModelBackend.user_can_authenticate``
        y en el login. La referencia llama al campo ``active``; se conserva ese
        nombre y se expone el alias, en vez de renombrar el campo.
        """
        return self.active

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
            # Evita disparar la señal de cambio en el re-hash.
            self._password = None
            self.save(update_fields=['password'])
        return hashers.check_password(raw_password, self.password, setter)

    def set_unusable_password(self):
        self.password = hashers.make_password(None)

    def has_usable_password(self):
        return hashers.is_password_usable(self.password)

    def get_session_auth_hash(self):
        """HMAC del hash de password: cambiarlo invalida las sesiones vivas."""
        return salted_hmac(
            _SESSION_AUTH_KEY_SALT, self.password, algorithm='sha256',
        ).hexdigest()

    def get_session_auth_fallback_hash(self):
        """Hashes bajo ``SECRET_KEY_FALLBACKS`` — mantiene válidas las sesiones
        durante la rotación de ``SECRET_KEY``."""
        for fallback_secret in settings.SECRET_KEY_FALLBACKS:
            yield salted_hmac(
                _SESSION_AUTH_KEY_SALT, self.password,
                secret=fallback_secret, algorithm='sha256',
            ).hexdigest()

    # --- Compañías permitidas (≙ ``company_id`` + ``company_ids``) ---
    #
    # ``company_ids`` **existe** como reverso del M2M declarado en
    # ``ResCompany.user_ids`` (``related_name='company_ids'``, tabla
    # ``res_company_users_rel`` con columnas ``cid``/``user_id``). La
    # referencia lo declara desde ambos lados con esos mismos nombres
    # (``odoo19c: res_users.py:247`` y ``res_company.py:68``; idem
    # ``odoo18c:`` en ``:403`` y ``:54``).
    #
    # Los dos campos son ejes distintos, no redundantes: ``company`` es la
    # compañía **activa por defecto**, ``company_ids`` el **conjunto
    # alcanzable sin volver a autenticarse**. El resolutor de ``ir_http``
    # ya consume ambos.

    def _check_user_company(self):
        """Odoo ``_check_user_company`` (``odoo19c: res_users.py:501-511``).

        ``@api.constrains('company_id', 'company_ids', 'active')``: para un
        usuario activo, su compañía por defecto tiene que estar entre las
        permitidas. Se porta como método explícito y se invoca desde
        ``clean()`` — Django no valida M2M en ``full_clean()`` porque la
        relación no existe hasta que la fila tiene PK.
        """
        if not self.active or self.company_id is None or self.pk is None:
            return
        if self.company_ids.filter(pk=self.company_id).exists():
            return
        permitidas = ', '.join(
            self.company_ids.values_list('partner__name', flat=True)) or '—'
        raise ValidationError(
            'La compañía %(company)s no está entre las permitidas para el '
            'usuario %(user)s (%(allowed)s).' % {
                'company': self.company.partner.name,
                'user': self.login,
                'allowed': permitidas,
            })

    def _permitted_company_ids(self):
        """Odoo ``_get_company_ids`` (``odoo19c: res_users.py:726-730``).

        La referencia filtra por ``('active', '=', True)`` — una compañía
        archivada no otorga acceso aunque siga en la tabla de relación. La
        propia va primero, porque ``env.company`` es la primera activada.
        """
        if self.pk is None:
            return ()
        activas = tuple(
            self.company_ids.filter(active=True).values_list('pk', flat=True))
        if self.company_id is None:
            return activas
        return (self.company_id,) + tuple(
            pk for pk in activas if pk != self.company_id)

    def clean(self):
        super().clean()
        self._check_user_company()

    # --- Presentación ---
    def get_full_name(self):
        return self.partner.name

    def get_short_name(self):
        return self.partner.name.split(' ', 1)[0] if self.partner.name else ''

    def deactivate(self, reason):
        """Desactiva la cuenta registrando la causa."""
        self.active = False
        self.deactivated_reason = reason
        self.deactivated_at = timezone.now()
        self.save(update_fields=[
            'active', 'deactivated_reason', 'deactivated_at', 'updated_at',
        ])

    # --- Eje interno / portal / público (≙ res_users.py:1165-1179) ---
    #
    # La referencia resuelve ``_is_internal``/``_is_portal``/``_is_public``
    # como ``has_group(base.group_user | group_portal | group_public)`` —
    # tres xmlid fijos. Aquí el eje NO es un grupo con nombre reservado: cada
    # ``res.groups`` declara su ``user_type`` (``ResGroups.USER_TYPE_*``), y
    # dos tipos distintos son disjuntos por construcción (ver
    # ``res_groups.py``). Así que "es interno" = "pertenece a ≥1 grupo cuyo
    # ``user_type`` es 'internal'". Esto es lo que el eje interno/portal
    # necesitaba y no existía: los consumidores (p. ej.
    # ``authz_totp_mail.totp_mail_required``, la re-ruta de invitación por
    # audiencia, los puentes ``_portal``) usaban ``partner.employee`` como
    # proxy — este es el criterio real.

    def _has_user_type(self, user_type):
        """True si pertenece a algún grupo con ese ``user_type``.

        ``group_ids`` es el reverso del M2M declarado en ``res_groups.py``
        (``related_name='group_ids'``); su ``user_type`` es la Selection de
        ``ResGroups.USER_TYPE_CHOICES``.
        """
        return self.group_ids.filter(user_type=user_type).exists()

    def is_internal(self):
        """≙ ``_is_internal`` (res_users.py:1165-1167)."""
        return self._has_user_type('internal')

    def is_portal(self):
        """≙ ``_is_portal`` (res_users.py:1169-1171)."""
        return self._has_user_type('portal')

    def is_public(self):
        """≙ ``_is_public`` (res_users.py:1173-1175)."""
        return self._has_user_type('public')

    @property
    def share(self):
        """≙ ``_compute_share`` (res_users.py:460-464): compartido = NO
        interno. Un usuario sin ningún grupo de tipo es 'share' (portal/
        público), igual que la referencia marca ``share=True`` a todo lo que
        no está en ``group_user``."""
        return not self.is_internal()


class ResUsersLog(TimeStampedModel):
    """``res.users.log`` — que hubo un acceso, no una auditoría.

    Fiel a ``odoo19c: odoo/addons/base/models/res_users.py:134-152``, y la
    fidelidad aquí **quita** cosas. La referencia declara **un solo campo**
    (``create_uid``) y se apoya en la fecha automática; su comentario lo dice::

        # Uses the magical fields `create_uid` and `create_date` for recording
        # logins. See `mail.presence` for more recent activity tracking.

    Y su ``_gc_user_logs`` conserva **una fila por usuario**, borrando el resto.
    No es un registro de auditoría: es un "último acceso" con historia mínima.

    El ``AuthEvent`` que murió con el addon ``users`` guardaba tipo de evento,
    IP y user-agent. Eso **no** vive aquí: la referencia lo pone en el
    dispositivo (``ResDeviceLog``: ``ip_address``, ``browser``, ``platform``).
    Portar ambos al mismo modelo habría fundido dos responsabilidades que la
    referencia mantiene separadas.
    """

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='logs',
        help_text='Usuario que accedió (Odoo create_uid).',
    )

    class Meta:
        db_table            = 'res_users_log'
        ordering            = ['-id']
        verbose_name        = 'Registro de acceso'
        verbose_name_plural = 'Registros de acceso'

    def __str__(self) -> str:
        return f'acceso de {self.user_id} el {self.created_at}'
