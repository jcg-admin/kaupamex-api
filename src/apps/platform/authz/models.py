"""Models — apps.platform.authz (modelo de capacidades propio, Opción B / DEC-AUTHZ-01).

Reemplaza la autorización nativa de Django. Vocabulario IGA (referencia
Oracle/Tuebora, patente US 9,489,390): *entitlement* = el vínculo
capacidad↔usuario (Direct = grant a la cuenta; Indirect = vía Role). El
superadmin es el titular del Role ``superadmin`` (DEC-01=B: el modelo de
usuario no tiene ``is_superuser`` nativo).

Diseño: :ref:`arq-mod-authz` (MOD-027). Entidades:

- ``Module`` / ``Capability`` — el catálogo de permisos (cara de negocio +
  ``code`` técnico ``dominio.verbo`` en un solo registro).
- ``Role`` + ``RoleAssignment`` — agrupación e indirect entitlement.
- ``DirectEntitlement`` + ``EntitlementRevocation`` — grant directo + tombstone
  auditable.
- ``AuthzEvent`` — auditoría append-only (403 + uso de capacidad sensible, DEC-07).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import AppendOnlyModel, TimeStampedModel


class Module(TimeStampedModel):
    """Agrupador de capacidades por dominio funcional (menú/navegación)."""
    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = models.CharField(max_length=100, verbose_name='Nombre')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    # Grafo de dependencias (SOL-085 S3): activar este módulo para una company
    # exige que sus ``depends`` estén activos (p.ej. pos depende de
    # inventory+catalogue). No simétrico: A depende de B ≠ B depende de A.
    depends = models.ManyToManyField(
        'self', symmetrical=False, related_name='dependents', blank=True,
        verbose_name='Depende de',
    )

    class Meta:
        db_table = 'authz_module'
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        ordering = ['code']

    def __str__(self):
        return self.code


class AccessLevel(models.IntegerChoices):
    """Nivel de acceso graduado (DEC-11, modelo NetSuite VIEW<CREATE<EDIT<FULL).

    ``NONE`` es el piso (ausencia de nivel). Los niveles son sucesivos: cada uno
    implica los inferiores (EDIT ⇒ CREATE ⇒ VIEW). El verbo de un ``code``
    ``dominio.verbo`` en un call-site expresa el nivel MÍNIMO requerido; se mapea
    con ``for_verb``.
    """
    NONE = 0, 'Ninguno'
    VIEW = 10, 'Ver'
    CREATE = 20, 'Crear'
    EDIT = 30, 'Editar'
    FULL = 40, 'Total'

    @classmethod
    def for_verb(cls, verb):
        """Nivel mínimo que exige un verbo CRUD; ``NONE`` si no es CRUD."""
        return {
            'view': cls.VIEW,
            'create': cls.CREATE,
            'edit': cls.EDIT,
            'full': cls.FULL,
        }.get(verb, cls.NONE)

    def implied_verbs(self):
        """Verbos CRUD que este nivel concede (para expandir noun→noun.verbo)."""
        verbs = []
        if self >= AccessLevel.VIEW:
            verbs.append('view')
        if self >= AccessLevel.CREATE:
            verbs.append('create')
        if self >= AccessLevel.EDIT:
            verbs.append('edit')
        if self >= AccessLevel.FULL:
            verbs.append('full')
        return verbs


class Capability(TimeStampedModel):
    """Un permiso atómico. ``code`` = ``dominio.verbo`` (cara técnica); el resto
    es la cara de negocio (un solo registro, sin split lógico/físico)."""
    module = models.ForeignKey(
        Module, on_delete=models.PROTECT, related_name='capabilities',
        verbose_name='Módulo',
    )
    code = models.CharField(
        max_length=100, unique=True,
        verbose_name='Código', help_text="Formato 'dominio.verbo' (p.ej. orders.refund).",
    )
    name = models.CharField(max_length=150, verbose_name='Nombre')
    description = models.TextField(blank=True, default='', verbose_name='Descripción')
    category = models.CharField(max_length=50, blank=True, default='', verbose_name='Categoría')
    is_sensitive = models.BooleanField(
        default=False, verbose_name='Sensible',
        help_text='Su uso exitoso se audita en AuthzEvent (DEC-07).',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        db_table = 'authz_capability'
        verbose_name = 'Capacidad'
        verbose_name_plural = 'Capacidades'
        ordering = ['code']

    def __str__(self):
        return self.code


class Role(TimeStampedModel):
    """Agrupación de capacidades. El acceso vía Role es *indirect entitlement*."""
    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = models.CharField(max_length=100, verbose_name='Nombre')
    capabilities = models.ManyToManyField(
        Capability, through='RoleCapability', related_name='roles', blank=True,
        verbose_name='Capacidades',
    )

    class Meta:
        db_table = 'authz_role'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['code']

    def __str__(self):
        return self.code


class RoleCapability(TimeStampedModel):
    """Grade de una capacidad dentro de un rol (through de ``Role.capabilities``,
    DEC-11). Reemplaza el M2M plano: cada par rol↔capacidad lleva su
    ``AccessLevel``. Para capacidades de acción nombrada (``code`` con punto que
    no es verbo CRUD, p.ej. ``account.profile``) el nivel es irrelevante y se
    guarda ``FULL`` — el resolver las trata por membresía, no por escala."""
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='role_capabilities',
        verbose_name='Rol',
    )
    capability = models.ForeignKey(
        Capability, on_delete=models.CASCADE, related_name='role_capabilities',
        verbose_name='Capacidad',
    )
    level = models.IntegerField(
        choices=AccessLevel.choices, default=AccessLevel.FULL,
        verbose_name='Nivel de acceso',
    )

    class Meta:
        db_table = 'authz_role_capability'
        verbose_name = 'Capacidad de rol'
        verbose_name_plural = 'Capacidades de rol'
        unique_together = [('role', 'capability')]
        ordering = ['role__code', 'capability__code']

    def __str__(self):
        return f'{self.role.code}:{self.capability.code}@{self.get_level_display()}'


class RoleAssignment(TimeStampedModel):
    """Asignación usuario↔Role (indirect entitlement). ``expires_at`` NULL = sin
    expiración (gancho JIT/least-privilege)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='role_assignments', verbose_name='Usuario',
    )
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name='assignments', verbose_name='Rol',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Asignado por',
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Expira')

    class Meta:
        db_table = 'authz_role_assignment'
        verbose_name = 'Asignación de rol'
        verbose_name_plural = 'Asignaciones de rol'
        constraints = [
            models.UniqueConstraint(fields=['user', 'role'], name='uq_authz_role_assignment'),
        ]
        indexes = [models.Index(fields=['user', 'role'])]

    def __str__(self):
        return f'{self.user_id} → {self.role_id}'


class DirectEntitlement(TimeStampedModel):
    """Grant directo positivo usuario↔Capability (direct entitlement, DEC-AUTHZ-01)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='direct_entitlements', verbose_name='Usuario',
    )
    capability = models.ForeignKey(
        Capability, on_delete=models.CASCADE, related_name='direct_entitlements',
        verbose_name='Capacidad',
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Otorgado por',
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Expira')

    class Meta:
        db_table = 'authz_direct_entitlement'
        verbose_name = 'Grant directo'
        verbose_name_plural = 'Grants directos'
        constraints = [
            models.UniqueConstraint(fields=['user', 'capability'], name='uq_authz_direct_entitlement'),
        ]
        indexes = [models.Index(fields=['user', 'capability'])]

    def __str__(self):
        return f'{self.user_id} +{self.capability_id}'


class EntitlementRevocation(TimeStampedModel):
    """Tombstone auditable: cancela un grant directo usuario↔Capability
    (DEC-AUTHZ-01). No cancela capacidades heredadas de rol."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='entitlement_revocations', verbose_name='Usuario',
    )
    capability = models.ForeignKey(
        Capability, on_delete=models.CASCADE, related_name='entitlement_revocations',
        verbose_name='Capacidad',
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Revocado por',
    )
    reason = models.TextField(blank=True, default='', verbose_name='Motivo')

    class Meta:
        db_table = 'authz_entitlement_revocation'
        verbose_name = 'Revocación de grant'
        verbose_name_plural = 'Revocaciones de grant'
        constraints = [
            models.UniqueConstraint(fields=['user', 'capability'], name='uq_authz_entitlement_revocation'),
        ]
        indexes = [models.Index(fields=['user', 'capability'])]

    def __str__(self):
        return f'{self.user_id} -{self.capability_id}'


class AuthzEvent(AppendOnlyModel):
    """Auditoría append-only de autorización (DEC-07): se emite en denegación
    (403) y en uso exitoso de una ``Capability.is_sensitive=True``. Mismo patrón
    que ``BusinessEvent``. PII-safe: no guarda tokens ni passwords."""
    ACTION_DENY = 'DENY'
    ACTION_SENSITIVE_USE = 'SENSITIVE_USE'
    ACTION_CHOICES = [
        (ACTION_DENY, 'Denegación (403)'),
        (ACTION_SENSITIVE_USE, 'Uso de capacidad sensible'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='authz_events', verbose_name='Actor',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True, verbose_name='Acción')
    capability_code = models.CharField(max_length=100, blank=True, default='', verbose_name='Capacidad')
    ip_addr = models.GenericIPAddressField(null=True, blank=True)
    correlation_id = models.CharField(max_length=32, blank=True, default='', db_index=True)
    extra_json = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'authz_event'
        verbose_name = 'Evento de autorización'
        verbose_name_plural = 'Eventos de autorización'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['actor', 'action', '-created_at']),
        ]

    def __str__(self):
        a = self.actor_id or 'anon'
        return f'AuthzEvent[{a}] {self.action} {self.capability_code}'


class ReauthSession(TimeStampedModel):
    """Sesión reautenticada — DEC-12 shape A.

    Ventana temporal, con TTL, abierta tras **re-autenticación**, dentro de la
    cual las acciones **sensibles** del usuario pasan sin re-teclear
    credenciales. **NO es una elevación de privilegios** (no se llama "sudo" a
    propósito): la elegibilidad es por **capacidad/Role** —nunca ``is_staff``,
    invariante SoD— y confirmar identidad **no otorga poderes nuevos**; sólo
    ratifica intención para las acciones sensibles que el Role del usuario ya
    autoriza (:ref:`analisis-diseno-reauth-sensibles-dec12`).

    Se ata a la **sesión** Django (``session_key``): una fila activa por
    ``(user, session_key)``. El gate vive en el permission class
    ``HasCapability`` (``assert_session_fresh``), no en un middleware. La
    apertura/cierre se auditan en ``AuthzEvent`` (DEC-07). Un cierre de sesión
    la deja huérfana; el barrido de expiradas lo hace la propia consulta
    (``expires_at__gt=now``).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='reauth_sessions', verbose_name='Usuario',
    )
    session_key = models.CharField(
        max_length=40, blank=True, default='', db_index=True,
        verbose_name='Clave de sesión',
        help_text='Sesión Django a la que se ata la reautenticación.',
    )
    started_at = models.DateTimeField(verbose_name='Iniciada')
    expires_at = models.DateTimeField(db_index=True, verbose_name='Expira')
    ip_addr = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')

    class Meta:
        db_table = 'authz_reauth_session'
        verbose_name = 'Sesión reautenticada'
        verbose_name_plural = 'Sesiones reautenticadas'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'session_key'], name='uq_authz_reauth_session',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'session_key', 'expires_at']),
        ]

    def is_active(self, now=None):
        return self.expires_at > (now or timezone.now())

    def __str__(self):
        return f'ReauthSession[{self.user_id}] → {self.expires_at:%Y-%m-%dT%H:%M}'


class MenuItem(TimeStampedModel):
    """Entrada del menú del panel admin (DEC-08/09).

    Proyección UX del catálogo de capacidades: el árbol de navegación se
    **persiste** (``authz_menu_item``, adjacency list vía ``parent``) y cada
    entrada se etiqueta con la ``Capability`` requerida para verla. La sección
    es un ``MenuItem`` de nivel 0 (``parent`` null, sin ``route``); sus hijos
    llevan la capacidad del dominio.

    NO es autorización: el candado real es ``HasCapability`` en cada vista
    (:ref:`analisis-enforcement-hascapability-isowner`). El menú solo decide
    **qué se muestra**; el endpoint ``me/menu/`` poda el árbol con
    ``resolve_capabilities`` para no filtrar destinos inaccesibles.

    ``audience`` separa el menú del **panel admin** del menú de **cuenta del
    comprador** (DEC-AUTHZ-BUYER): ambos son registro-dirigidos y podados por
    capacidad, pero se sirven por separado (``me/menu/?audience=account``). Así
    agregar una entrada de cualquiera de los dos menús es sembrar una fila —
    sin tocar la navegación del UI (que ya no lleva la lista fija ni la
    negación).
    """
    AUDIENCE_ADMIN = 'admin'
    AUDIENCE_ACCOUNT = 'account'
    AUDIENCE_CHOICES = [
        (AUDIENCE_ADMIN, 'Panel admin'),
        (AUDIENCE_ACCOUNT, 'Cuenta del comprador'),
    ]

    audience = models.CharField(
        max_length=10, choices=AUDIENCE_CHOICES, default=AUDIENCE_ADMIN,
        db_index=True, verbose_name='Audiencia',
        help_text="'admin' = panel; 'account' = menú de cuenta del comprador.",
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name='Sección padre',
        help_text='Null = sección de nivel 0.',
    )
    key = models.CharField(
        max_length=80, unique=True, verbose_name='Clave',
        help_text='Slug estable del item (para seed idempotente).',
    )
    label = models.CharField(max_length=80, verbose_name='Etiqueta')
    route = models.CharField(
        max_length=160, blank=True, default='', verbose_name='Ruta SPA',
        help_text="Ruta del router React (p.ej. '/admin/products'). Vacío en secciones.",
    )
    icon = models.CharField(max_length=40, blank=True, default='', verbose_name='Icono')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    required_capability = models.ForeignKey(
        Capability, on_delete=models.PROTECT, null=True, blank=True,
        related_name='menu_items', verbose_name='Capacidad requerida',
        help_text='Null = visible para cualquier admin (p.ej. secciones).',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        db_table = 'authz_menu_item'
        verbose_name = 'Entrada de menú'
        verbose_name_plural = 'Entradas de menú'
        ordering = ['parent_id', 'order', 'id']
        indexes = [
            models.Index(fields=['parent', 'order']),
        ]

    def __str__(self):
        return f'{self.key} ({self.label})'
