"""Models — apps.platform.company (capa L1 de la plataforma Kaupamex).

Diseño: :ref:`analisis-modelo-tenant-l1-foundation` (plataforma-kaupamex).
Entidad L1 = ``Company`` (DEC-T7; converge Odoo ``res.company`` / NetSuite).

- ``Company`` — el cliente/organización que contrata Kaupamex. Raíz L1: **no**
  tiene FK a la capa L0 (la relación operador↔company es operacional, no de
  datos). Paralelo ``res.company`` de Odoo / ``Organizer`` de pretix.
- ``CompanyModuleSubscription`` — qué ``Module`` (``apps.platform.authz``) tiene
  contratado cada company, con vigencia. Es la puerta **L1-a** (módulo activo
  sí/no) que el resolver compone con el catálogo L2 (DEC-11), expuesta como
  ``Company.active_module_codes()``.

``price`` es un placeholder de facturación (valor, no lógica): el modelo de
precios sigue abierto (pregunta abierta del diseño) y no cambia el esquema.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.platform.company.context import get_current_company
from apps.core.models import TimeStampedModel


class CompanyScopedManager(models.Manager):
    """Manager de aislamiento de fila L3 (SOL-085). ``for_current_company()``
    filtra por la ``Company`` del contexto del request, **fail-closed**: sin
    company en contexto → queryset vacío (denegar por defecto), nunca "todo".

    Requiere que el modelo tenga una FK ``company`` (columna ``company_id``).
    El acceso cross-company del operador L0 usa el manager por defecto
    (``objects``), explícito y no ambiguo.
    """

    def for_current_company(self):
        company_id = get_current_company()
        if company_id is None:
            return self.get_queryset().none()
        return self.get_queryset().filter(company_id=company_id)


# Códigos canónicos de companies especiales (SOL-085 S3, lección L-EXT-3).
# - Founder: primer tenant L1 real (PracticaYoruba); target de backfill de las
#   filas de dominio existentes al colgar la FK ``company`` (S3).
# - System: company de datos compartidos de plataforma (``is_system=True``);
#   los datos globales (SEPOMEX, referencia) cuelgan de aquí, con fallback por
#   whitelist en el manager scopeado — NO ``company_id`` nullable.
FOUNDER_COMPANY_CODE = 'practicayoruba'
SYSTEM_COMPANY_CODE = 'kaupamex_global'


class Company(TimeStampedModel):
    """Cliente/organización que contrata la plataforma (raíz L1, DEC-T7)."""

    class Status(models.TextChoices):
        TRIAL = 'trial', 'En prueba'
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        CANCELLED = 'cancelled', 'Cancelado'

    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = models.CharField(max_length=150, verbose_name='Nombre')
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.TRIAL,
        verbose_name='Estado',
    )
    # Company de datos compartidos de plataforma (L-EXT-3). Los datos globales
    # cuelgan de la system company; el manager scopeado hace fallback por
    # whitelist a ella además de la company activa. NO usar company nullable.
    is_system = models.BooleanField(
        default=False, verbose_name='Company de sistema',
        help_text='Company de datos compartidos de plataforma (L0), no un tenant.',
    )
    # Datos mínimos de facturación (opcionales hasta activar).
    billing_email = models.EmailField(blank=True, default='', verbose_name='Correo de facturación')
    billing_name = models.CharField(max_length=150, blank=True, default='', verbose_name='Razón social')
    tax_id = models.CharField(max_length=30, blank=True, default='', verbose_name='RFC / Tax ID')

    class Meta:
        db_table = 'company'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['code']

    def __str__(self):
        return self.code

    @classmethod
    def get_founder(cls):
        """Founder company (PracticaYoruba) — target de backfill de S3. Idempotente."""
        obj, _ = cls.objects.get_or_create(
            code=FOUNDER_COMPANY_CODE,
            defaults={'name': 'PracticaYoruba', 'status': cls.Status.ACTIVE},
        )
        return obj

    @classmethod
    def get_system(cls):
        """System company (datos compartidos de plataforma, L-EXT-3). Idempotente."""
        obj, _ = cls.objects.get_or_create(
            code=SYSTEM_COMPANY_CODE,
            defaults={'name': 'Kaupamex (plataforma)', 'status': cls.Status.ACTIVE,
                      'is_system': True},
        )
        return obj

    def active_module_codes(self, now=None):
        """Set de ``Module.code`` con suscripción **activa** (L1-a).

        El resolver compone esto: ``caps L2 filtradas por
        c.module in company.active_module_codes()``.
        """
        if now is None:
            now = timezone.now()
        codes = set()
        for sub in self.subscriptions.select_related('module').all():
            if sub.is_active(now):
                codes.add(sub.module.code)
        return codes


class Subsidiary(TimeStampedModel):
    """Entidad legal bajo la ``Company`` (jerarquía OneWorld → root).

    Scope **L3**, NO multi-tenancy: la ``Company`` es el tenant; la subsidiaria
    es una entidad legal dentro de él. Sirve a la vez como atributo org del
    empleado y como dimensión de restricción del rol (DIS-03). Frontera MVP:
    consolidación inter-company, tax nexus y multi-moneda contable quedan FUERA
    (DIS-02) — sólo subsidiaria como scope + pertenencia.
    """

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='subsidiaries',
        verbose_name='Empresa (tenant)',
    )
    name = models.CharField(max_length=150, verbose_name='Nombre')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='Subsidiaria padre',
    )
    country = models.CharField(max_length=2, blank=True, default='', verbose_name='País')
    base_currency = models.CharField(
        max_length=3, blank=True, default='MXN', verbose_name='Moneda base',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        db_table = 'org_subsidiary'
        verbose_name = 'Subsidiaria'
        verbose_name_plural = 'Subsidiarias'
        ordering = ['company__code', 'name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent', 'SUBSIDIARY_CYCLE')


class Department(TimeStampedModel):
    """Unidad organizativa dentro de una subsidiaria (con sub-departamentos)."""

    subsidiary = models.ForeignKey(
        Subsidiary, on_delete=models.CASCADE, related_name='departments',
        verbose_name='Subsidiaria',
    )
    name = models.CharField(max_length=150, verbose_name='Nombre')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='Departamento padre',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'org_department'
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        ordering = ['subsidiary__name', 'name']

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _reject_hierarchy_cycle(self, 'parent', 'DEPARTMENT_CYCLE')


class Job(TimeStampedModel):
    """Catálogo de puestos. El departamento es opcional (puesto transversal)."""

    title = models.CharField(max_length=150, verbose_name='Puesto')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jobs', verbose_name='Departamento',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'org_job'
        verbose_name = 'Puesto'
        verbose_name_plural = 'Puestos'
        ordering = ['title']

    def __str__(self):
        return self.title


def _reject_hierarchy_cycle(node, fk_name, error_code):
    """Rechaza que ``node`` sea su propio ancestro por ``fk_name`` (DIS-04).

    Recorre la cadena de padres; si vuelve a ``node`` (o a sí mismo), lanza
    ``ValidationError`` con ``error_code`` en inglés (canon ``codigo_error``).
    Nodos aún sin pk (creación) no pueden cerrar un ciclo salvo auto-padre.
    """
    parent = getattr(node, fk_name, None)
    if parent is None:
        return
    if parent.pk is not None and parent.pk == node.pk:
        raise ValidationError({fk_name: error_code})
    seen = set()
    while parent is not None:
        if parent.pk == node.pk:
            raise ValidationError({fk_name: error_code})
        if parent.pk in seen:
            break
        seen.add(parent.pk)
        parent = getattr(parent, fk_name, None)


class ModulePrice(TimeStampedModel):
    """Catálogo de tarifas por ``Module`` × ciclo, con vigencia (DEC-T6, S4).

    Versiona tarifas sin mutar histórico: un cambio de precio cierra la fila
    vigente (``effective_to``) y abre una nueva. Al suscribir, el precio
    vigente se **copia** a la ``CompanyModuleSubscription`` — el catálogo NO se
    referencia en vivo (inmutabilidad histórica: cambiar la tarifa no reescribe
    lo que una company ya paga).

    Los montos son **datos** que el operador L0 (Kaupamex) siembra; este modelo
    es solo la estructura — no fija precios (pricing = #180).
    """

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Mensual'
        ANNUAL = 'annual', 'Anual'

    module = models.ForeignKey(
        'authz.Module', on_delete=models.PROTECT, related_name='prices',
        verbose_name='Módulo',
    )
    billing_cycle = models.CharField(
        max_length=8, choices=BillingCycle.choices, verbose_name='Ciclo de cobro',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio')
    currency = models.CharField(max_length=3, default='MXN', verbose_name='Moneda')
    effective_from = models.DateTimeField(verbose_name='Vigente desde')
    effective_to = models.DateTimeField(
        null=True, blank=True, verbose_name='Vigente hasta',
    )

    class Meta:
        db_table = 'module_price'
        verbose_name = 'Tarifa de módulo'
        verbose_name_plural = 'Tarifas de módulo'
        ordering = ['module__code', 'billing_cycle', '-effective_from']
        indexes = [
            models.Index(fields=['module', 'billing_cycle', 'effective_from']),
        ]

    def __str__(self):
        return f'{self.module_id}:{self.billing_cycle}:{self.price}'

    @classmethod
    def current(cls, module, billing_cycle, at=None):
        """Tarifa vigente de ``module`` × ``billing_cycle`` en ``at`` (default
        ahora), o ``None`` si no hay ninguna sembrada/activa.

        Vigente = ``effective_from <= at`` y (``effective_to`` nulo o
        ``> at``). Ante solapamiento (cambio de tarifa), gana la de
        ``effective_from`` más reciente (orden del ``Meta``).
        """
        if at is None:
            at = timezone.now()
        return (
            cls.objects
            .filter(module=module, billing_cycle=billing_cycle,
                    effective_from__lte=at)
            .filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gt=at))
            .order_by('-effective_from')
            .first()
        )


class CompanyModuleSubscription(TimeStampedModel):
    """Módulo contratado por una company, con vigencia (puerta L1-a)."""

    class Status(models.TextChoices):
        TRIAL = 'trial', 'En prueba'
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        CANCELLED = 'cancelled', 'Cancelado'

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='subscriptions',
        verbose_name='Empresa',
    )
    module = models.ForeignKey(
        'authz.Module', on_delete=models.PROTECT, related_name='subscriptions',
        verbose_name='Módulo',
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ACTIVE,
        verbose_name='Estado',
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Inicio')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Expira')
    # Ciclo + precio COPIADOS del catálogo ``ModulePrice`` al suscribir (DEC-T6,
    # S4). No se referencia el catálogo en vivo: la copia congela lo que la
    # company paga (inmutabilidad histórica). ``price`` nulo = sin tarifa
    # sembrada (free) — no un error.
    billing_cycle = models.CharField(
        max_length=8, choices=ModulePrice.BillingCycle.choices,
        blank=True, default='', verbose_name='Ciclo de cobro',
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Precio',
    )

    objects = models.Manager()               # default: cross-company (L0)
    scoped = CompanyScopedManager()          # L3: fail-closed por company

    class Meta:
        db_table = 'company_module_subscription'
        verbose_name = 'Suscripción de módulo'
        verbose_name_plural = 'Suscripciones de módulo'
        ordering = ['company__code', 'module__code']
        unique_together = [('company', 'module')]

    def __str__(self):
        return f'{self.company.code}:{self.module_id}'

    def is_active(self, now=None):
        """True si la suscripción está ``ACTIVE`` y no expiró."""
        if self.status != self.Status.ACTIVE:
            return False
        if self.expires_at is None:
            return True
        if now is None:
            now = timezone.now()
        return self.expires_at > now

    def missing_dependencies(self, now=None):
        """Set de ``Module.code`` que este módulo declara como ``depends`` pero
        que la company **no** tiene activos (grafo de dependencias, S3).

        Chequeo de deps directas: es transitivamente correcto porque el módulo
        del que depende no pudo activarse sin las suyas.
        """
        required = set(self.module.depends.values_list('code', flat=True))
        if not required:
            return set()
        return required - self.company.active_module_codes(now) - {self.module.code}

    def apply_current_price(self, at=None):
        """Copia la tarifa vigente de ``ModulePrice`` a esta suscripción (S4).

        Usa ``self.billing_cycle`` (elegido al contratar) para elegir la fila.
        Congela ``price`` — el catálogo NO se referencia en vivo. Si no hay
        tarifa vigente (módulo sin precio sembrado / free), deja ``price`` en
        ``None``. No hace ``save()``: el llamador persiste.
        """
        if not self.billing_cycle or self.module_id is None:
            return
        current = ModulePrice.current(self.module, self.billing_cycle, at=at)
        self.price = current.price if current is not None else None

    def save(self, *args, **kwargs):
        # Gate de activación: una suscripción ACTIVE exige sus dependencias
        # activas (SOL-085 S3). Las no-activas (trial/suspended/cancelled) se
        # guardan sin chequeo — aún no conceden nada.
        if self.status == self.Status.ACTIVE:
            missing = self.missing_dependencies()
            if missing:
                raise ValidationError({
                    'module': (
                        f"El módulo '{self.module.code}' requiere módulos activos "
                        f"que la empresa no tiene: {', '.join(sorted(missing))}."
                    )
                })
        super().save(*args, **kwargs)
