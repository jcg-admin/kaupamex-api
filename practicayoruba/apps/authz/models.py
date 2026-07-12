"""Models — apps.authz (modelo de capacidades propio, Opción B / DEC-AUTHZ-01).

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

from apps.core.models import AppendOnlyModel, TimeStampedModel


class Module(TimeStampedModel):
    """Agrupador de capacidades por dominio funcional (menú/navegación)."""
    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = models.CharField(max_length=100, verbose_name='Nombre')
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'authz_module'
        verbose_name = 'Módulo'
        verbose_name_plural = 'Módulos'
        ordering = ['code']

    def __str__(self):
        return self.code


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
        Capability, related_name='roles', blank=True, verbose_name='Capacidades',
    )

    class Meta:
        db_table = 'authz_role'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['code']

    def __str__(self):
        return self.code


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
