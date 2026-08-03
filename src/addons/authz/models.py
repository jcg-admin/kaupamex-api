"""Models — addons.authz (modelo de capacidades propio, Opción B / DEC-AUTHZ-01).

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
import fields
import models
from django.utils import timezone

from addons.base.models import TimeStampedModel


class Module(TimeStampedModel):
    """Agrupador de capacidades por dominio funcional (menú/navegación).

    Además de agrupar capacidades, es el **catálogo L0** de módulos vendibles
    de Kaupamex (:ref:`diseno-catalogo-l0-module-extendido`). La metadata de
    catálogo calca el contrato ``__manifest__`` de Odoo: ``is_application``
    (vendible vs técnico ← ``application``), ``tier`` (free/paid ←
    ``license``), ``category``/``version``/``description`` y ``auto_install``.
    El tier de pago vive en la metadata, no en la carpeta (principio Odoo).
    El precio efectivo por company vive en ``CompanyModuleSubscription.price``.
    """

    class Tier(models.TextChoices):
        """Nivel de cobro del módulo (← manifest ``license``: LGPL-3 vs OEEL-1)."""
        FREE = 'free', 'Gratis'
        PAID = 'paid', 'De pago'

    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = fields.Char(max_length=100, verbose_name='Nombre')
    is_active = fields.Boolean(default=True, verbose_name='Activo')
    # Grafo de dependencias (SOL-085 S3): activar este módulo para una company
    # exige que sus ``depends`` estén activos (p.ej. pos depende de
    # inventory+catalogue). No simétrico: A depende de B ≠ B depende de A.
    depends = fields.Many2many(
        'self', symmetrical=False, related_name='dependents', blank=True,
        verbose_name='Depende de',
    )
    # Metadata de catálogo L0 (contrato __manifest__ de Odoo).
    is_application = fields.Boolean(
        default=False, verbose_name='App vendible',
        help_text='Vendible (top-level) vs módulo técnico (dependencia interna).',
    )
    tier = fields.Selection(
        max_length=8, choices=Tier.choices, default=Tier.FREE,
        verbose_name='Tier',
    )
    category = fields.Char(
        max_length=50, blank=True, default='', verbose_name='Categoría',
    )
    version = fields.Char(
        max_length=20, blank=True, default='', verbose_name='Versión',
    )
    description = fields.Text(
        blank=True, default='', verbose_name='Descripción',
    )
    auto_install = fields.Boolean(
        default=False, verbose_name='Auto-instalar',
        help_text='Se activa solo cuando sus dependencias están presentes.',
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
    module = fields.Many2one(
        Module, on_delete=models.PROTECT, related_name='capabilities',
        verbose_name='Módulo',
    )
    code = fields.Char(
        max_length=100, unique=True,
        verbose_name='Código', help_text="Formato 'dominio.verbo' (p.ej. orders.refund).",
    )
    name = fields.Char(max_length=150, verbose_name='Nombre')
    description = fields.Text(blank=True, default='', verbose_name='Descripción')
    category = fields.Char(max_length=50, blank=True, default='', verbose_name='Categoría')
    is_sensitive = fields.Boolean(
        default=False, verbose_name='Sensible',
        help_text='Su uso exitoso se audita en AuthzEvent (DEC-07).',
    )
    is_active = fields.Boolean(default=True, verbose_name='Activa')

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
    name = fields.Char(max_length=100, verbose_name='Nombre')
    capabilities = fields.Many2many(
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
    role = fields.Many2one(
        Role, on_delete=models.CASCADE, related_name='role_capabilities',
        verbose_name='Rol',
    )
    capability = fields.Many2one(
        Capability, on_delete=models.CASCADE, related_name='role_capabilities',
        verbose_name='Capacidad',
    )
    level = fields.Integer(
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
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='role_assignments', verbose_name='Usuario',
    )
    role = fields.Many2one(
        Role, on_delete=models.CASCADE, related_name='assignments', verbose_name='Rol',
    )
    assigned_by = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Asignado por',
    )
    expires_at = fields.Datetime(null=True, blank=True, verbose_name='Expira')

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
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='direct_entitlements', verbose_name='Usuario',
    )
    capability = fields.Many2one(
        Capability, on_delete=models.CASCADE, related_name='direct_entitlements',
        verbose_name='Capacidad',
    )
    granted_by = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Otorgado por',
    )
    expires_at = fields.Datetime(null=True, blank=True, verbose_name='Expira')

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
    user = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='entitlement_revocations', verbose_name='Usuario',
    )
    capability = fields.Many2one(
        Capability, on_delete=models.CASCADE, related_name='entitlement_revocations',
        verbose_name='Capacidad',
    )
    revoked_by = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Revocado por',
    )
    reason = fields.Text(blank=True, default='', verbose_name='Motivo')

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


# Modelos movidos a apps de feature opcional al estilo Odoo (SOL-094 frente B,
# DEC-01), con tabla física intacta (SeparateDatabaseAndState):
#   - AuthzEvent (auditoría DEC-07)     -> ``addons.authz_audit``  (~ account_audit_trail)
#   - ReauthSession (step-up DEC-12)    -> ``addons.authz_reauth`` (~ authz_totp)
# Importar desde ``addons.authz_audit.models`` / ``addons.authz_reauth.models``
# respectivamente.
#
# El menú (antes ``MenuItem`` en ``addons.authz_menu``) se movió a
# ``base.IrUiMenu`` — tabla ``ir_ui_menu``. En la referencia ``ir.ui.menu`` vive
# en ``base``, junto al motor de permisos, y el addon intermedio no aportaba
# nada: el modelo es del núcleo, no una feature opcional.
