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
import binascii
import logging
import os
from datetime import timedelta

import api
import fields
import models

from django.apps import apps
from django.conf import settings
from django.contrib.auth import hashers
from django.core.exceptions import ValidationError
from django.db.models import F
from django.db.models.functions import Length
from django.db.models.lookups import Exact
from django.utils import timezone
from django.utils.crypto import salted_hmac

from addons.base.models import signals
from addons.base.models.timestamped_mixin import TimeStampedModel
from exceptions import AccessDenied, AccessError, UserError
from orm.environments import get_current_user, is_su

#: Registro del bloque de claves de API — ≙ el ``_logger`` de módulo que la
#: referencia declara en la cabecera de ``res_users.py``.
_apikeys_logger = logging.getLogger(__name__)

# Sal del HMAC de sesión. Literal de Django (``AbstractBaseUser``): cambiarlo
# invalidaría toda sesión viva, así que se replica verbatim.
_SESSION_AUTH_KEY_SALT = (
    'django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash'
)

#: El grupo "funciones técnicas". La referencia lo hace efectivo sólo en modo
#: depuración (``res_users.py:1080-1082``); aquí no hay tal modo — ver
#: :meth:`ResUsers.has_group`.
GROUP_NO_ONE_XMLID = 'base.group_no_one'

#: El grupo de usuario interno. Es el que la guarda de :meth:`ResUsers.has_group`
#: exige a quien pregunta por los grupos de otro.
GROUP_USER_XMLID = 'base.group_user'


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

    def _create_user(self, login, password, partner=None, group_ids=None,
                     **extra_fields):
        """Crea la credencial **con sus grupos ya aplicados**.

        ``group_ids`` replica el campo homónimo de ``res.users`` en la
        referencia (``odoo19c: odoo/addons/base/models/res_users.py:257``),
        que viaja dentro de ``vals`` y queda escrito cuando ``create()``
        retorna. Por eso el propio ``create`` de la referencia puede leer
        ``user._is_internal()`` (``:583``) y ``user.share`` (``:590``) sobre
        lo que acaba de crear, y por eso el override de ``digest`` funciona.

        En Django el M2M sólo se escribe una vez que la fila tiene PK, así
        que aquí se aplica explícitamente entre el ``save()`` y el retorno.
        Quien reciba el usuario lo recibe en el mismo estado que en la
        referencia. Ver H-API-304.
        """
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
        if group_ids:
            user.group_ids.set(group_ids)
        # Equivalente del punto en que ``super().create()`` retorna en la
        # referencia: la credencial existe y sus grupos están escritos. Los
        # satélites (``digest``) escuchan aquí; ``base`` no los importa.
        signals.res_users_created.send(sender=self.model, user=user)
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

    Los cinco atributos de clase (H-API-618, tarea #385)
    -----------------------------------------------------

    La fuente los declara en ``:163-167``; aquí van los cinco, con su forma
    Django derivada al lado cuando existe:

    - ``_inherits`` — el destino de la delegación. **El mecanismo ya estaba**
      (``orm/inherits.py``, tarea #88, aplicado en ``BaseConfig.ready()``); lo
      que faltaba era la declaración, que es de donde ese cableado ahora lee su
      par delegado→FK en vez de tenerlo escrito a mano. El valor de la FK es
      ``partner``, no ``partner_id``: este árbol suprime el sufijo ``_id``.
    - ``_order = 'name, login'`` → ``Meta.ordering = ['partner__name',
      'login']``. ``name`` **no es columna** de ``res_users``: la fuente lo
      obtiene del partner por la misma delegación, y aquí eso es el lookup de
      la FK. Antes decía ``['login']`` — divergencia silenciosa, ahora cerrada.
    - ``_allow_sudo_commands = False`` — la fuente lo declara explícito: este
      modelo **no** admite comandos con privilegio.
    - ``_name`` y ``_description`` — verbatim; ``_description`` convive con
      ``Meta.verbose_name``, no lo sustituye.

    **El objeto de tabla ``_login_key``** (``UNIQUE (login)``, ``:274``) ya
    existe y con el nombre de la referencia: ``login`` se declara
    ``unique=True`` y PostgreSQL nombra el constraint ``res_users_login_key``
    — verificado con ``pg_constraint``. No hace falta un ``Meta.constraints``
    para renombrarlo.
    """

    _name                 = 'res.users'
    _description          = 'User'
    _inherits             = {'res.partner': 'partner'}
    _order                = 'name, login'
    _allow_sudo_commands  = False

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
        # Derivado de ``_order = 'name, login'``: ``name`` vive en el partner
        # delegado, así que aquí es el lookup de la FK.
        ordering            = ['partner__name', 'login']
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

    # --- Pertenencia a grupo por identificador externo (≙ :1034-1096) ---
    #
    # La referencia resuelve el xmlid contra
    # ``res.groups._get_group_definitions().get_id(...)``, una caché del grafo
    # de grupos que este árbol no tiene. Aquí la resolución va por
    # ``ir.model.data`` —el mismo camino que ``env.ref`` toma allá— y la
    # clausura transitiva sale de ``ResGroups.all_implied_by_ids``, que ya
    # estaba portada.
    #
    # El puente entre ambas es una identidad, no una aproximación: la fuente
    # pregunta ``group_id in user.all_group_ids`` con
    # ``all_group_ids = group_ids.all_implied_ids`` (``:447-449``), es decir
    # «¿algún grupo mío implica a G?». Leída desde G, esa misma arista es
    # ``G.all_implied_by_ids``. Es exactamente el cómputo que
    # ``ResGroups.all_user_ids`` ya hacía en este árbol, visto desde el
    # usuario en vez de desde el grupo.
    #
    # ``ResGroups`` se resuelve por el registro de apps y no por import:
    # ``res_groups.py`` importa ``ResUsers`` para declarar su M2M, así que un
    # import en esta dirección cerraría el ciclo. Mismo criterio —y mismo
    # mecanismo— que ``_partner_model()`` de arriba.

    @property
    def all_group_ids(self):
        """≙ ``all_group_ids`` (``:258-259``) — los grupos del usuario, cerrados
        transitivamente.

        La fuente lo declara como ``Many2many`` calculado, y su cómputo es una
        línea: ``user.all_group_ids = user.group_ids.all_implied_ids``
        (``_compute_all_group_ids``, ``:447-449``). Aquí es una ``property``
        sobre la misma clausura ya portada — mismo resultado, sin motor de
        cómputo almacenado.

        Es **reflexiva**: incluye los grupos propios del usuario, no sólo los
        implicados. Lo garantiza ``ResGroups._closure``, cuyo BFS marca cada
        semilla como visitada antes de expandirla.

        ``ResGroups`` se resuelve por el registro de apps y no por import, por
        la misma razón que el bloque de arriba: ``res_groups.py`` importa
        ``ResUsers`` para declarar su M2M, así que un import en esta dirección
        cerraría el ciclo. Mismo mecanismo que ``_partner_model()``.

        Su primer consumidor es ``ResUsersApikeys._check_expiration_date``, que
        lee ``api_key_duration`` de estos grupos.
        """
        groups = apps.get_model('base', 'ResGroups')
        seeds = list(self.group_ids.all())
        return groups.objects.filter(
            pk__in=groups._closure(seeds, lambda g: g.implied_ids.all()))

    def has_groups(self, group_spec: str) -> bool:
        """¿Satisface ``self`` las restricciones de grupo de ``group_spec``?

        Verdadero cuando el usuario pertenece a **al menos uno** de los grupos
        positivos y a **ninguno** de los precedidos por ``!``.

        ``group_spec`` es una lista separada por comas de identificadores
        externos totalmente calificados, cada uno opcionalmente precedido por
        ``!`` — p. ej. ``"base.group_user,base.group_portal,!base.group_system"``.

        Tres detalles de la fuente que se conservan porque cambian el
        resultado, no la forma:

        - El punto solo (``"."``) es falso por definición: es el marcador de
          "ningún grupo satisface esto" del cargador de vistas.
        - Los negativos se evalúan **primero**, por coste: un negativo que
          acierta corta sin tocar los positivos.
        - Un ``group_spec`` **sólo** de negativos que no aciertan es
          verdadero (``return not positives``). No es un caso de borde
          decorativo: ``"!base.group_system"`` significa "cualquiera que no
          sea administrador", y con la lectura contraria no designaría a nadie.

        Igual que en :meth:`has_group`, ``base.group_no_one`` no es efectivo
        aquí — ver el porqué en ese método.
        """
        if group_spec == '.':
            return False

        positives = []
        negatives = []
        for group_ext_id in group_spec.split(','):
            group_ext_id = group_ext_id.strip()
            if group_ext_id.startswith('!'):
                negatives.append(group_ext_id[1:])
            else:
                positives.append(group_ext_id)

        # Por coste, los negativos primero — verbatim de la fuente.
        if any(self.has_group(ext_id) for ext_id in negatives):
            return False
        if any(self.has_group(ext_id) for ext_id in positives):
            return True
        return not positives

    def has_group(self, group_ext_id: str) -> bool:
        """¿Pertenece ``self`` al grupo de ese identificador externo?

        ``group_ext_id`` va **totalmente calificado** (``modulo.ext_id``): no
        hay módulo implícito con el que completarlo.

        Dos diferencias con :meth:`_has_group`, y las dos son de la fuente:

        **1. La guarda de acceso.** La referencia levanta ``AccessError`` si
        quien llama no está elevado, no se está preguntando por sí mismo, y no
        es un usuario interno (``:1077-1080``); su comentario dice para qué:
        *"this prevents RPC calls from non-internal users to retrieve
        information about other users"*.

        Aquí el actor sale de ``orm.environments`` (``is_su`` / la PK del
        usuario en contexto), no de un ``env`` recibido. Eso añade un cuarto
        estado que la referencia no tiene: **no hay actor en contexto**. Le
        pasa a todo lo que corre fuera de una petición —cron, migraciones,
        tests— y se resuelve como permitido, porque ahí no existe la llamada
        RPC de la que la guarda protege. Denegarlo haría inusable el método
        justo donde nadie está autenticándose.

        **2. ``base.group_no_one``.** La fuente lo hace efectivo **sólo** en
        modo depuración (``result and bool(request and request.session.debug)``).
        Este árbol **no tiene modo desarrollador**: el matiz queda BLOQUEADO
        por ``request.session.debug`` — no existe tal interruptor aquí.
        Sucesor: tarea #450.

        Mientras tanto la decisión es **fail-closed y explícita**: este método
        devuelve ``False`` para ``base.group_no_one`` aunque el usuario esté en
        el grupo. Es la lectura fiel de "sólo efectivo en depuración" cuando no
        hay depuración, y **no es una precaución teórica**: el propio XML de la
        fuente declara ``group_no_one.implied_by_ids = [group_user,
        group_system]`` (``base_groups.xml:58``), así que **todo** usuario
        interno lo tiene por implicación. Sin el matiz, las funciones técnicas
        quedarían encendidas para todos y para siempre — que es exactamente lo
        que la comprobación de depuración impide allá.

        Quien necesite la pertenencia cruda tiene :meth:`_has_group`, que es
        justo el método que la fuente deja sin el matiz.
        """
        if not (is_su() or self._caller_may_query_groups()):
            raise AccessError(
                'has_group() sólo puede consultarse sobre el usuario actual.')
        if group_ext_id == GROUP_NO_ONE_XMLID:
            # Sin modo desarrollador el grupo nunca es efectivo (ver docstring).
            return False
        return self._has_group(group_ext_id)

    def _caller_may_query_groups(self) -> bool:
        """¿Puede el actor en contexto preguntar por los grupos de ``self``?

        **No es un símbolo de la referencia**: allá la condición cabe en la
        línea de la guarda porque ``self.env.user`` siempre existe. Aquí hay
        que distinguir el caso "sin actor" del caso "actor ajeno", y meter esa
        distinción dentro del ``if`` lo volvía ilegible.

        Sin actor en contexto → permitido (código de servidor, no RPC).
        Con actor → o es uno mismo, o es interno (``base.group_user``).
        """
        actor = get_current_user()
        if actor is None:
            return True
        if actor.pk == self.pk:
            return True
        return actor._has_group(GROUP_USER_XMLID)

    def _has_group(self, group_ext_id: str) -> bool:
        """Pertenencia cruda al grupo, sin guarda ni matiz de depuración.

        :param str group_ext_id: identificador externo (XML ID) del grupo,
           **totalmente calificado** (``modulo.ext_id``).
        :return: ``True`` si ``self`` es miembro del grupo, explícita o
           implícitamente (algún grupo suyo lo implica, directa o
           transitivamente).

        Devuelve ``False`` —en vez de fallar— cuando el identificador no
        resuelve, resuelve a algo que no es un grupo, o el usuario todavía no
        tiene PK. Es la misma postura fail-closed que la fuente da a un
        ``group_id`` ausente de ``all_group_ids``: un grupo que no existe no
        otorga pertenencia.
        """
        if self.pk is None:
            return False
        data_model = apps.get_model('base', 'IrModelData')
        group = data_model.ref(group_ext_id, raise_if_not_found=False)
        if not isinstance(group, apps.get_model('base', 'ResGroups')):
            return False
        implying = list(group.all_implied_by_ids.values_list('pk', flat=True))
        return self.group_ids.filter(pk__in=implying).exists()

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

    # ------------------------------------------------------------------
    # Segundo factor — el eslabón BASE de una cadena de tres
    #
    # Los dos métodos devuelven ``None`` a propósito: son el fondo sobre el
    # que cada addon de 2FA aporta lo suyo. La referencia los declara aquí
    # con el mismo cuerpo vacío (``odoo/addons/base/models/res_users.py``,
    # ``_mfa_type`` y ``_mfa_url``), y los extiende dos veces:
    #
    #   base (None) → auth_totp ('totp') → auth_totp_mail ('totp_mail')
    #
    # Cada eslabón consulta ``super()`` PRIMERO y sólo aporta si el interno
    # calló, así que la precedencia la gana el más interno. Aquí eso se
    # expresa con ``combine=keep_previous`` en ``extend_model`` — ver
    # ``orm.method_chain.keep_previous``, que documenta por qué el relevo por
    # defecto daría la precedencia contraria.
    # ------------------------------------------------------------------

    def _mfa_type(self):
        """Si hay un método de MFA activo, devuelve su tipo como cadena."""
        return

    def _mfa_url(self):
        """Si hay un método de MFA activo, devuelve la URL de su segundo paso."""
        return


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


# =========================================================================
# Soporte de claves de API — ≙ ``# API keys support`` (``:1518-1750``)
#
# La referencia declara este bloque **en este mismo archivo**, después de
# ``res.users``: constantes de módulo, el modelo ``res.users.apikeys``, la
# función ``_check_apikey_credentials`` y dos modelos transitorios de su
# formulario web. El sitio se conserva por
# ``atributos-de-clase-de-modelo.md`` cláusula 2 — inventar un
# ``res_users_apikeys.py`` habría creado un archivo que la referencia no
# tiene, que es el defecto de :ref:`h-api-578`.
#
# Su primer consumidor NO es la integración externa sino el **dispositivo de
# confianza** del segundo factor: ``auth_totp.device`` declara
# ``_inherit = ["res.users.apikeys"]`` y guarda ahí la cookie ``td_id``
# (``odoo19c: auth_totp/models/auth_totp.py:16``). Por eso este bloque entra
# con la tarea #716 y no con #490, que es la superficie RPC.
# =========================================================================

#: ≙ ``API_KEY_SIZE`` (``:1519``) — bytes de entropía de la clave.
API_KEY_SIZE = 20

#: ≙ ``INDEX_SIZE`` (``:1520``) — dígitos hexadecimales del prefijo indexado,
#: «4 bytes, o el 20 % de la clave». Es lo que permite buscar la fila sin
#: comparar el hash de todas.
INDEX_SIZE = 8

#: ≙ ``DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT`` (``:1527``).
DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT = 10

#: ≙ ``KEY_CRYPT_CONTEXT`` (``:1521-1526``).
#:
#: La referencia usa ``passlib.CryptContext(['pbkdf2_sha512'],
#: pbkdf2_sha512__rounds=6000)`` y explica la elección: *"default is 29000
#: rounds which is 25~50ms, which is probably unnecessary given in this case
#: all the keys are completely random data: dictionary attacks on API keys
#: isn't much of a concern"*.
#:
#: ``passlib`` no está en este árbol (medido: 0 en ``pyproject.toml``); el
#: mecanismo equivalente son los *hashers* de Django, que este archivo ya usa
#: para la contraseña. Se instancia la clase directamente en vez de
#: registrarla en ``PASSWORD_HASHERS``: así el número de rondas queda atado a
#: **este** uso y no cambia el coste de verificar una contraseña.
#:
#: La familia cambia de ``sha512`` a ``sha256`` porque es la que Django trae;
#: el argumento de la referencia —entropía completa, no hay ataque de
#: diccionario— no distingue entre las dos.
KEY_HASHER = hashers.PBKDF2PasswordHasher()
KEY_HASHER_ITERATIONS = 6000


def _hash_api_key(key):
    """Codifica una clave con :data:`KEY_HASHER` — ≙ ``KEY_CRYPT_CONTEXT.hash``."""
    hasher = hashers.PBKDF2PasswordHasher()
    hasher.iterations = KEY_HASHER_ITERATIONS
    return hasher.encode(key, hasher.salt())


def _verify_api_key(key, encoded):
    """≙ ``KEY_CRYPT_CONTEXT.verify`` — comparación en tiempo constante."""
    return hashers.check_password(key, encoded)


class _ResUsersApikeysBase(TimeStampedModel):
    """Campos y mecanismo de ``res.users.apikeys`` — abstracta, sin tabla.

    Portación de ``odoo19c: odoo/addons/base/models/res_users.py:1519-1720``
    (LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

    **Por qué es abstracta.** La referencia declara un segundo modelo sobre
    éste: ``auth_totp.device`` lleva ``_name`` propio **y**
    ``_inherit = ["res.users.apikeys"]`` (``odoo19c:
    auth_totp/models/auth_totp.py:15-16``). Ese constructo es herencia por
    **prototipo**: el hijo copia campos y métodos y obtiene **tabla aparte**,
    no comparte filas con el padre. La forma Django del prototipo es una base
    abstracta, que es la misma adaptación que ``res_device.py`` ya hace para
    ``res.device`` sobre ``res.device.log``.

    Sus métodos son ``classmethod`` precisamente por esto: ``cls`` es el
    modelo sobre el que se invocan, así que ``auth_totp.device._generate``
    escribe en la tabla de dispositivos y ``res.users.apikeys._generate`` en la
    de claves, sin que ninguno de los dos sepa del otro. Es el mismo reparto
    que la fuente logra pasando el nombre de tabla a
    ``_check_apikey_credentials``.

    La FK a usuario **no** vive aquí: la declara cada concreto, para conservar
    su propio ``related_name`` (``api_keys`` / ``totp_trusted_devices``). Una
    base abstracta obligaría a nombrarlo con ``%(class)s``, que es lo que
    ``res_device.py`` evita por la misma razón.

    **Lo que la hace distinta de un token cualquiera** es el par
    ``index``/``key``: la clave completa **nunca** se guarda. Se guarda su
    hash (``key``) y su prefijo de 8 hexadecimales en claro (``index``), que
    es lo único por lo que se puede buscar. Sin ese prefijo habría que
    verificar el hash de cada fila de la tabla en cada petición.

    Divergencias declaradas
    =======================

    1. **``_auto = False`` y ``init()``.** La referencia desactiva la creación
       automática de tabla y la emite a mano con ``CREATE TABLE`` porque
       ``key`` e ``index`` **no pueden ser campos del ORM**: cualquier lectura
       genérica los expondría. Aquí el ORM es Django y la tabla la crea su
       migración, así que las dos columnas se declaran como campos y su
       protección es la misma que la del secreto TOTP
       (``authz_totp/models/totp_secret.py``): ningún serializer las nombra.

       El contenido de ``init()`` no se pierde — se reparte en su forma
       declarativa, que es lo que ``atributos-de-clase-de-modelo.md`` prescribe
       para los objetos de tabla:

       - ``CREATE INDEX … (user_id, index)`` → ``Meta.indexes``
       - ``CHECK (char_length(index) = 8)`` → ``Meta.constraints``
       - ``ON DELETE CASCADE`` sobre ``user_id`` → ``on_delete=CASCADE``

    2. **``remove()`` pierde su ``@check_identity``.** En la referencia el
       decorador vive en ``base`` y envuelve el método del modelo, porque su
       RPC expone modelos directamente. Aquí la identidad fresca la exige
       ``authz_reauth.assert_session_fresh`` desde la **vista** (DEC-12), y
       ``base`` no puede depender de ``authz_reauth`` sin invertir el grafo.
       Así que ``remove()`` y ``_remove()`` quedan como los dos métodos que la
       referencia declara —el público con su comprobación de propiedad, el
       interno sin ella— y el gate de identidad lo pone quien los exponga.

    3. **``_assert_can_auth`` no existe en este árbol** (medido: 0 hits). Es
       el limitador de intentos que la referencia envuelve alrededor de
       ``generate``/``revoke``. Los dos métodos se portan **sin** él y el
       hueco queda declarado: sucesor **#726**.

    4. **El SQL crudo se expresa con el ORM.** La referencia lo necesita
       porque ``key``/``index`` no son campos suyos; aquí sí lo son, así que
       ``INSERT`` → ``objects.create``, el ``SELECT`` con ``JOIN res_users`` →
       ``filter(user__active=True, …)`` y el ``DELETE`` del barrido →
       ``.delete()``. Mismo predicado, misma semántica.

    5. **Los dos modelos de asistente NO se portan** —
       ``res.users.apikeys.description`` (``:1753``, transitorio, 6 defs) y
       ``res.users.apikeys.show`` (``:1837``, abstracto, 0 defs)—. Su cuerpo
       entero es la forma del diálogo del backoffice OWL: un selector de
       duración, un ``make_key`` que devuelve un ``ir.actions.act_window``
       hacia el segundo modelo, y un segundo modelo cuya única razón de existir
       es sostener un campo de sólo lectura dentro de esa ventana modal. Aquí
       el cliente es React (#488) y el equivalente es un endpoint que devuelve
       la clave en el cuerpo de la respuesta, con su ``@extend_schema`` y su
       gate de capacidad — sucesor **#490**.

       **Lo que NO es presentación se mide aparte**, porque un veredicto de
       "asistente" lo habría barrido con el resto:

       - el tope de duración por grupo (``api_key_duration``) **sí está
         portado**: ``_selection_duration`` sólo filtra la lista que ofrece,
         y la regla que decide vive en ``_check_expiration_date``;
       - ``check_access_make_key`` —*"Only internal users can create API
         keys"*— **no tiene contraparte todavía**. Es una regla de negocio, no
         de diálogo: la pone quien exponga el endpoint, y ``_is_internal()``
         ya existe en este árbol para expresarla.
    """

    name = fields.Char(
        verbose_name='Descripción',
        help_text='Odoo name ("Description") — para qué es esta clave.',
    )
    scope = fields.Char(
        null=True, blank=True,
        verbose_name='Ámbito',
        help_text='Odoo scope. NULL da acceso a cualquier RPC; con valor, '
                  'sólo a ese ámbito ("rpc", "browser").',
    )
    expiration_date = fields.Datetime(
        null=True, blank=True,
        verbose_name='Fecha de caducidad',
        help_text='Odoo expiration_date. NULL es una clave permanente, que '
                  'sólo un usuario de sistema puede crear.',
    )
    index = fields.Char(
        max_length=INDEX_SIZE, db_index=True,
        verbose_name='Prefijo',
        help_text='Odoo index — los primeros 8 hexadecimales de la clave, en '
                  'claro. Es por lo que se busca la fila; NO es la clave.',
    )
    key = fields.Char(
        verbose_name='Clave (hash)',
        help_text='Odoo key — el hash de la clave completa. SECRETO: ningún '
                  'serializer lo expone, igual que el secreto TOTP.',
    )

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f'{self.name} ({self.index})'

    def remove(self):
        """≙ ``remove`` (``:1556-1558``) — el punto de entrada público.

        La referencia lo decora con ``@check_identity``; aquí ese gate vive en
        la vista (divergencia 2). El método se conserva porque la referencia
        declara **dos** —público e interno— y fundirlos borraría la distinción
        que su propio docstring explica.
        """
        return self._remove()

    def _remove(self):
        """≙ ``_remove`` (``:1559-1572``).

        Su docstring de la fuente, verbatim: *"Use the remove() method to
        remove an API Key. This method implement logic, but won't check the
        identity (mainly used to remove trusted devices)"* — y ese paréntesis
        es exactamente el consumidor que la tarea #716 desbloquea.
        """
        actor = get_current_user()
        if is_su() or self.user_id == getattr(actor, 'pk', None):
            _apikeys_logger.info(
                "API key(s) removed: scope: <%s> for '%s' (#%s)",
                self.scope, getattr(actor, 'login', 'n/a'),
                getattr(actor, 'pk', None),
            )
            self.delete()
            return
        raise AccessError(
            'No puede retirar claves de API que no sean suyas, salvo que sea '
            'un usuario de sistema.'
        )

    @classmethod
    def _check_credentials(cls, *, scope, key):
        """≙ ``_check_credentials`` (``:1574-1575``).

        Es ``classmethod`` y no método de instancia porque la referencia lo
        llama sobre el modelo vacío (``self.env['res.users.apikeys']``), que
        aquí no tiene equivalente de instancia.
        """
        return _check_apikey_credentials(scope=scope, key=key, model=cls)

    @classmethod
    def _check_expiration_date(cls, date):
        """≙ ``_check_expiration_date`` (``:1577-1587``).

        Tres reglas de la fuente, conservadas: un usuario de sistema puede
        todo; el resto **debe** poner fecha; y esa fecha no puede exceder el
        máximo que sus grupos permitan (``api_key_duration``, en días).

        ``api_key_duration`` ya estaba portado en ``res.groups`` con un
        docstring que decía *"este árbol … no tiene API keys que lo
        consuman"*. Este método es ese consumidor — el stub deja de
        racionalizar su ausencia (:ref:`h-api-638`).
        """
        if is_su():
            return
        actor = get_current_user()
        if not date:
            raise ValidationError('La clave de API debe tener fecha de caducidad.')
        durations = [
            group.api_key_duration
            for group in actor.all_group_ids
            if group.api_key_duration
        ] if actor is not None else []
        max_duration = max(durations) if durations else 1.0
        if date > timezone.now() + timedelta(days=max_duration):
            raise ValidationError(
                f'No puede exceder {max_duration} días.'
            )

    @classmethod
    def _generate(cls, scope, name, expiration_date):
        """≙ ``_generate`` (``:1589-1616``) — genera una clave y la devuelve.

        Su docstring de la fuente conserva la advertencia que importa: *"This
        method must be called in sudo to use a duration greater than that
        allowed by the user's privileges. For a persistent key (infinite
        duration), no value for expiration date."*

        La clave en claro se devuelve **una sola vez**: lo que queda en la
        tabla es su hash. La fuente lo dice con un comentario en el sitio —
        *"no need to clear the LRU when adding a key, only when removing"*—
        que aquí no tiene receptor porque no hay caché de claves.
        """
        cls._check_expiration_date(expiration_date)
        k = binascii.hexlify(os.urandom(API_KEY_SIZE)).decode()
        actor = get_current_user()
        cls.objects.create(
            name=name,
            user_id=getattr(actor, 'pk', None),
            scope=scope,
            expiration_date=expiration_date or None,
            key=_hash_api_key(k),
            index=k[:INDEX_SIZE],
        )
        _apikeys_logger.info(
            "%s generated: scope: <%s> for '%s' (#%s)",
            cls._description, scope, getattr(actor, 'login', 'n/a'),
            getattr(actor, 'pk', None),
        )
        return k

    @classmethod
    def _ensure_can_manage_keys_programmatically(cls):
        """≙ ``_ensure_can_manage_keys_programmatically`` (``:1618-1633``).

        El comentario largo de la fuente explica por qué el administrador es
        una excepción y no depende del parámetro: habilitar, llamar y
        restaurar son tres pasos no atómicos, y un fallo entre el segundo y el
        tercero dejaría la gestión abierta para todos.
        """
        icp = apps.get_model('base', 'SystemParameter')
        enabled = icp.get_param('base.enable_programmatic_api_keys', 'False')
        if not (is_su() or str(enabled).lower() in ('1', 'true', 'yes')):
            raise UserError('La gestión programática de claves de API no está habilitada.')

    @classmethod
    @api.model
    def generate(cls, key, scope, name, expiration_date):
        """≙ ``generate`` (``:1634-1684``) — una clave nueva a partir de otra viva.

        Las reglas de compatibilidad de ámbito son las de la fuente, verbatim
        en su comentario: *"A global key can generate credentials for any
        scope (including global). A scoped key can only generate credentials
        for its own scope."*

        **Sin el limitador de intentos** de la fuente
        (``_assert_can_auth``) — divergencia 3, sucesor #726.
        """
        cls._ensure_can_manage_keys_programmatically()
        actor = get_current_user()
        uid = getattr(actor, 'pk', None)
        now = timezone.now()
        nb_keys = cls.objects.filter(
            models.Q(expiration_date__isnull=True) | models.Q(expiration_date__gte=now),
            user_id=uid,
        ).count()
        icp = apps.get_model('base', 'SystemParameter')
        try:
            nb_keys_limit = int(icp.get_param(
                'base.programmatic_api_keys_limit',
                DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT))
        except (TypeError, ValueError):
            _apikeys_logger.warning(
                "Invalid value for 'base.programmatic_api_keys_limit', "
                "using default value.")
            nb_keys_limit = DEFAULT_PROGRAMMATIC_API_KEYS_LIMIT
        if nb_keys >= nb_keys_limit:
            raise UserError(
                f'Se alcanzó el límite de {nb_keys_limit} claves de API para '
                f'creación programática.')

        checked_uid = cls._check_credentials(scope=scope or 'rpc', key=key)
        if not checked_uid or checked_uid != uid:
            raise AccessDenied(
                'La clave de API dada no es válida o no pertenece al usuario actual.')
        new_key = cls._generate(scope, name, expiration_date)
        _apikeys_logger.info("%s %r generated from %r", cls._description,
                             new_key[:INDEX_SIZE], key[:INDEX_SIZE])
        return new_key

    @classmethod
    @api.model
    def revoke(cls, key):
        """≙ ``revoke`` (``:1685-1711``) — retira una clave viva.

        Recorre las filas cuyo prefijo coincide y verifica el hash de cada
        una, porque el prefijo **no** es único: es el mismo bucle de la
        fuente. Sin el limitador de intentos — divergencia 3.
        """
        cls._ensure_can_manage_keys_programmatically()
        assert key, 'key required'
        now = timezone.now()
        candidates = cls.objects.filter(
            models.Q(expiration_date__isnull=True) | models.Q(expiration_date__gte=now),
            index=key[:INDEX_SIZE],
        )
        for candidate in candidates:
            if _verify_api_key(key, candidate.key):
                candidate._remove()
                return True
        raise AccessDenied('La clave de API dada no es válida.')

    @classmethod
    @api.autovacuum
    def _gc_user_apikeys(cls):
        """≙ ``_gc_user_apikeys`` (``:1712-1720``) — barre las caducadas."""
        deleted, _ = cls.objects.filter(
            expiration_date__isnull=False,
            expiration_date__lt=timezone.now(),
        ).delete()
        _apikeys_logger.info("GC %r delete %d entries", cls._name, deleted)


class ResUsersApikeys(_ResUsersApikeysBase):
    """``res.users.apikeys`` — la clave de API de integración externa.

    El concreto del prototipo: aporta el nombre del modelo, su tabla y la FK a
    usuario; los campos y los diez métodos vienen de
    :class:`_ResUsersApikeysBase`, que documenta el mecanismo y sus cuatro
    divergencias.

    Su hermano por prototipo es ``auth_totp.device``
    (``addons/authz_totp/models/auth_totp.py``), que declara la **misma** forma
    sobre **otra** tabla.
    """

    _name = 'res.users.apikeys'
    _description = 'Users API Keys'
    #: La referencia lo declara ``False`` para emitir la tabla a mano
    #: (divergencia 1). Aquí la tabla la gestiona Django, así que el atributo
    #: se conserva **verbatim** como declaración de procedencia y su forma
    #: efectiva es ``Meta.managed = True``.
    _auto = False
    _allow_sudo_commands = False

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='api_keys',
        help_text='Odoo user_id — el dueño de la clave.',
    )

    class Meta:
        db_table            = 'res_users_apikeys'
        ordering            = ['-id']
        verbose_name        = 'Clave de API'
        verbose_name_plural = 'Claves de API'
        indexes = [
            # ≙ el ``CREATE INDEX … ON %(table)s (user_id, index)`` de
            # ``init()`` (``:1548-1555``). El nombre lo fija la referencia por
            # convención ``<tabla>_user_id_index_idx``; aquí se conserva.
            models.Index(fields=['user', 'index'],
                         name='res_users_apikeys_user_id_index_idx'),
        ]
        constraints = [
            # ≙ ``CHECK (char_length(index) = %(index_size)s)`` (``:1541``).
            #
            # NO se usa ``Q(index__length=…)``: Django no registra ``__length``
            # como lookup de ``CharField`` — medido, ``FieldError: Unsupported
            # lookup 'length'``. La forma que sí compila es la que
            # ``account_group.py`` ya verificó con ``constraint_sql()``:
            # ``Exact`` sobre ``Length``, que emite el ``char_length`` de la
            # fuente sin mutar el lookup global.
            models.CheckConstraint(
                condition=Exact(Length(F('index')), INDEX_SIZE),
                name='res_users_apikeys_index_size',
                violation_error_code='API_KEY_INDEX_SIZE',
            ),
        ]


def _check_apikey_credentials(*, scope, key, model=None):
    """≙ ``_check_apikey_credentials`` (``:1722-1750``).

    Devuelve el ``user_id`` si la clave es válida, ``None`` si no. El
    predicado es el de la fuente, término a término: el usuario **activo**, el
    prefijo coincidente, el ámbito nulo o igual, y la fecha nula o futura.

    La fuente recibe un cursor y el nombre de tabla porque el modelo hijo
    (``auth_totp.device``) comparte esta función con **otra** tabla; aquí ese
    parámetro es el modelo, por la misma razón y con la misma consecuencia: un
    dispositivo de confianza no valida contra las claves de RPC.
    """
    assert scope and key, 'scope and key required'
    if model is None:
        model = ResUsersApikeys
    now = timezone.now()
    candidates = model.objects.filter(
        models.Q(scope__isnull=True) | models.Q(scope=scope),
        models.Q(expiration_date__isnull=True) | models.Q(expiration_date__gte=now),
        user__active=True,
        index=key[:INDEX_SIZE],
    ).values_list('user_id', 'key')
    for user_id, current_key in candidates:
        if _verify_api_key(key, current_key):
            return user_id
    return None
