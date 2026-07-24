"""Models — addons.company (capa L1 de la plataforma Kaupamex).

Diseño: :ref:`analisis-modelo-tenant-l1-foundation` (plataforma-kaupamex).
Entidad L1 = ``Company`` (DEC-T7; converge Odoo ``res.company`` / NetSuite).

- ``Company`` — el cliente/organización que contrata Kaupamex. Raíz L1: **no**
  tiene FK a la capa L0 (la relación operador↔company es operacional, no de
  datos). Paralelo ``res.company`` de Odoo / ``Organizer`` de pretix.
- ``CompanyModuleSubscription`` — qué ``Module`` (``addons.authz``) tiene
  contratado cada company, con vigencia. Es la puerta **L1-a** (módulo activo
  sí/no) que el resolver compone con el catálogo L2 (DEC-11), expuesta como
  ``Company.active_module_codes()``.

``price`` es un placeholder de facturación (valor, no lógica): el modelo de
precios sigue abierto (pregunta abierta del diseño) y no cambia el esquema.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
import fields
import models
from django.utils import timezone

from addons.base_vat.validators import validate_rfc
from addons.company.context import company_scope, get_current_company
from addons.base.models import TimeStampedModel


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

# Valores L1 de contacto/newsletter/transaccional de PracticaYoruba (founder
# tenant, SOL-090 slice 3 + follow-up #199), sembrados como sus propios
# ``CompanySetting`` por las migraciones de datos
# ``company/0006_seed_founder_settings`` (contacto/newsletter) y
# ``company/0007_seed_founder_notifications_from`` (transaccional). Tal cual
# existían en ``config.settings.base`` (``CONTACT_FROM_EMAIL``/
# ``CONTACT_NOTIFY_EMAIL``/``NEWSLETTER_FROM_EMAIL``/``DEFAULT_FROM_EMAIL``)
# antes de estas slices — PracticaYoruba es tenant L1 (NO L0/Kaupamex), así
# que no eran stale, sólo estaban mal ubicados como ``default=`` global.
#
# ``notifications.from_email`` es el remitente **no-reply transaccional único**
# del tenant: bajo el diseño previo TODO el correo transaccional (auth,
# órdenes, envíos, devoluciones, soporte) salía de un solo ``DEFAULT_FROM_EMAIL``
# (``noreply@``). Se conserva esa unicidad como una sola clave per-tenant, en
# vez de una clave por addon.
#
# Constante módulo-nivel (dato, no comportamiento) para que la migración y los
# tests reseed la compartan sin duplicarla (mismo patrón que
# ``_DEFAULT_PARAMETERS`` en ``addons.base.models``).
FOUNDER_L1_SETTINGS = {
    'contact.from_email': 'hola@practicayoruba.com',
    'contact.notify_email': 'hola@practicayoruba.com',
    'newsletter.from_email': 'newsletter@practicayoruba.com',
    'notifications.from_email': 'noreply@practicayoruba.com',
}


class Company(TimeStampedModel):
    """Cliente/organización que contrata la plataforma (raíz L1, DEC-T7)."""

    class Status(models.TextChoices):
        TRIAL = 'trial', 'En prueba'
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        CANCELLED = 'cancelled', 'Cancelado'

    code = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    name = fields.Char(max_length=150, verbose_name='Nombre')
    status = fields.Selection(
        max_length=12, choices=Status.choices, default=Status.TRIAL,
        verbose_name='Estado',
    )
    # Company de datos compartidos de plataforma (L-EXT-3). Los datos globales
    # cuelgan de la system company; el manager scopeado hace fallback por
    # whitelist a ella además de la company activa. NO usar company nullable.
    is_system = fields.Boolean(
        default=False, verbose_name='Company de sistema',
        help_text='Company de datos compartidos de plataforma (L0), no un tenant.',
    )
    # Datos mínimos de facturación (opcionales hasta activar).
    billing_email = models.EmailField(blank=True, default='', verbose_name='Correo de facturación')
    billing_name = fields.Char(max_length=150, blank=True, default='', verbose_name='Razón social')
    tax_id = fields.Char(
        max_length=30, blank=True, default='', verbose_name='RFC / Tax ID',
        validators=[validate_rfc],
        help_text='RFC del SAT (12 moral / 13 física). Validado por base_vat.',
    )

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


class CompanySetting(TimeStampedModel):
    """Almacén de pares clave/valor de configuración **per-empresa** (L3).

    Diseño: :ref:`analisis-estrategia-configuracion-capas` (capa L3, sección
    7). Cierra :ref:`hallazgos-implementar-systemparameter-l2` (H-CFG-IMPL-10).
    Extiende el patrón L2 de ``addons.base.SystemParameter`` (equivalente
    Django de ``ir.config_parameter``: store key/value) a la dimensión
    per-compañía, con FK ``company`` + ``CompanyScopedManager`` (SOL-085) —
    el mismo par ``objects``/``scoped`` que ``CompanyModuleSubscription``.

    Bajo DB-per-company (SOL-091) este es un modelo de **dominio**: el
    ``CompanyDatabaseRouter`` lo enruta a ``company_<N>_db`` cuando esa base
    existe (N>1) y degenera a ``default`` bajo N=1 (no está en
    ``MULTIDB_CONTROL_PLANE_APPS`` — ``company`` ya es dominio ahí, igual que
    ``Company``/``CompanyModuleSubscription``). La FK ``company`` se conserva
    en AMBOS regímenes: bajo N=1 (o incluso bajo N>1, ver
    ``TestSol085RowScopingIntraBase`` en
    ``tests/integration/platform/test_multidb_isolation.py``) varias
    empresas pueden co-residir en la misma base física — el aislamiento de
    fila (SOL-085) es una capa distinta y necesaria además del aislamiento
    por base (SOL-091), no redundante con él.

    **L0 (Kaupamex, operador) vs L1 (PracticaYoruba, founder tenant).**
    PracticaYoruba es un **tenant L1** (``FOUNDER_COMPANY_CODE``), NO L0 —
    Kaupamex es L0 (el operador de la plataforma). Por eso los valores
    ``hola@practicayoruba.com`` / ``newsletter@practicayoruba.com`` (antes
    ``default=`` de ``config.settings.base``) NO eran stale: son la config
    **L1 correcta** de ese tenant, y la migración ``0006`` los siembra como
    filas de ``CompanySetting`` de PracticaYoruba (no los reemplaza por un
    valor de Kaupamex). El fallback de ``get_setting`` (sin empresa activa o
    sin fila para esa empresa) sí es **neutral, nivel Kaupamex** —
    PracticaYoruba es solo uno de potencialmente varios tenants. Contrástese
    con L2 (``addons.base.SystemParameter``): ``backup.alert_email`` →
    ``admin@kaupamex.com`` es correcto ahí porque el alertamiento de backups
    es infra **L0** (plataforma), sin dimensión de empresa — a diferencia de
    contacto/newsletter, que sí son per-tenant.
    """

    company = fields.Many2one(
        Company, on_delete=models.CASCADE, related_name='settings',
        verbose_name='Empresa',
    )
    key = fields.Char(max_length=255, verbose_name='Clave')
    value = fields.Text(verbose_name='Valor')

    objects = models.Manager()               # cross-company (L0 admin)
    scoped = CompanyScopedManager()          # L3: fail-closed por company activa

    class Meta:
        db_table = 'company_setting'
        verbose_name = 'Configuración de empresa'
        verbose_name_plural = 'Configuraciones de empresa'
        ordering = ['company_id', 'key']
        unique_together = [('company', 'key')]

    def __str__(self):
        return f'{self.company_id}:{self.key}'

    @staticmethod
    def _resolve_company_id(company):
        """``company`` puede ser ``None`` (usa la empresa ambiente del
        contexto), una instancia ``Company``, o un pk. Devuelve el pk o
        ``None`` si no hay empresa resoluble."""
        if company is None:
            return get_current_company()
        if isinstance(company, Company):
            return company.pk
        return company

    @classmethod
    def get_setting(cls, key, default=None, company=None):
        """Devuelve el valor de ``key`` de ``company`` (o de la empresa
        ambiente del contexto si ``company`` es ``None``), o ``default`` si
        no hay empresa resoluble o no existe la fila.

        A diferencia de ``SystemParameter.get_param`` (L2, sin dimensión de
        empresa), "sin empresa resoluble" es un caso legítimo aquí — no un
        error — mientras el resolutor subdominio→company (UC-PLT-06) no
        exista: un request anónimo sin empresa en contexto cae a ``default``
        sin tocar la BD.

        Envuelve la consulta en ``company_scope(company_id)`` para que el
        ``CompanyDatabaseRouter`` enrute a la base correcta aun si se llama
        con un ``company`` explícito distinto de (o fuera de) la empresa
        ambiente (p. ej. desde un job sin contexto de request).
        """
        company_id = cls._resolve_company_id(company)
        if company_id is None:
            return default
        with company_scope(company_id):
            value = (cls.objects
                     .filter(company_id=company_id, key=key)
                     .values_list('value', flat=True)
                     .first())
        return value if value is not None else default

    @classmethod
    def set_setting(cls, key, value, company):
        """Fija ``value`` para ``key`` de ``company``. ``company`` es
        **obligatorio** (a diferencia de ``get_setting``): no existe un "de
        qué empresa" ambiente razonable al escribir configuración.
        """
        company_id = cls._resolve_company_id(company)
        if company_id is None:
            raise ValueError(
                'CompanySetting.set_setting requiere una empresa resoluble '
                '(pasar company= explícito o tener company_scope activo).'
            )
        with company_scope(company_id):
            obj, created = cls.objects.get_or_create(
                company_id=company_id, key=key, defaults={'value': str(value)},
            )
            if not created and obj.value != str(value):
                obj.value = str(value)
                obj.save(update_fields=['value', 'updated_at'])
        return obj


class Subsidiary(TimeStampedModel):
    """Entidad legal bajo la ``Company`` (jerarquía OneWorld → root).

    Scope **L3**, NO multi-tenancy: la ``Company`` es el tenant; la subsidiaria
    es una entidad legal dentro de él. Sirve a la vez como atributo org del
    empleado y como dimensión de restricción del rol (DIS-03). Frontera MVP:
    consolidación inter-company, tax nexus y multi-moneda contable quedan FUERA
    (DIS-02) — sólo subsidiaria como scope + pertenencia.
    """

    company = fields.Many2one(
        Company, on_delete=models.CASCADE, related_name='subsidiaries',
        verbose_name='Empresa (tenant)',
    )
    name = fields.Char(max_length=150, verbose_name='Nombre')
    parent = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='Subsidiaria padre',
    )
    country = fields.Char(max_length=2, blank=True, default='', verbose_name='País')
    base_currency = fields.Char(
        max_length=3, blank=True, default='MXN', verbose_name='Moneda base',
    )
    is_active = fields.Boolean(default=True, verbose_name='Activa')

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

    subsidiary = fields.Many2one(
        Subsidiary, on_delete=models.CASCADE, related_name='departments',
        verbose_name='Subsidiaria',
    )
    name = fields.Char(max_length=150, verbose_name='Nombre')
    parent = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', verbose_name='Departamento padre',
    )
    is_active = fields.Boolean(default=True, verbose_name='Activo')

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

    title = fields.Char(max_length=150, verbose_name='Puesto')
    department = fields.Many2one(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='jobs', verbose_name='Departamento',
    )
    is_active = fields.Boolean(default=True, verbose_name='Activo')

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

    module = fields.Many2one(
        'authz.Module', on_delete=models.PROTECT, related_name='prices',
        verbose_name='Módulo',
    )
    billing_cycle = fields.Selection(
        max_length=8, choices=BillingCycle.choices, verbose_name='Ciclo de cobro',
    )
    price = fields.Monetary(max_digits=10, decimal_places=2, verbose_name='Precio')
    currency = fields.Char(max_length=3, default='MXN', verbose_name='Moneda')
    effective_from = fields.Datetime(verbose_name='Vigente desde')
    effective_to = fields.Datetime(
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

    company = fields.Many2one(
        Company, on_delete=models.CASCADE, related_name='subscriptions',
        verbose_name='Empresa',
    )
    module = fields.Many2one(
        'authz.Module', on_delete=models.PROTECT, related_name='subscriptions',
        verbose_name='Módulo',
    )
    status = fields.Selection(
        max_length=12, choices=Status.choices, default=Status.ACTIVE,
        verbose_name='Estado',
    )
    started_at = fields.Datetime(null=True, blank=True, verbose_name='Inicio')
    expires_at = fields.Datetime(null=True, blank=True, verbose_name='Expira')
    # Ciclo + precio COPIADOS del catálogo ``ModulePrice`` al suscribir (DEC-T6,
    # S4). No se referencia el catálogo en vivo: la copia congela lo que la
    # company paga (inmutabilidad histórica). ``price`` nulo = sin tarifa
    # sembrada (free) — no un error.
    billing_cycle = fields.Selection(
        max_length=8, choices=ModulePrice.BillingCycle.choices,
        blank=True, default='', verbose_name='Ciclo de cobro',
    )
    price = fields.Monetary(
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


class SubscriptionBillingRun(TimeStampedModel):
    """Corrida periódica de facturación L0 (UC-PLT-18 / #180).

    La mitad *cash* del O2C re-domiciliado (DEC-KX-07): el Actor Tiempo (o el
    operador) dispara una corrida por período; ésta emite las
    ``SubscriptionInvoice`` de las suscripciones vencidas y cobra. Persiste el
    **resumen auditable** que el ``run_billing`` sin estado no tenía (H-API-01/
    H-API-02). Ver :ref:`diseno-motor-facturacion-recurrente-l0`.
    """

    class TriggeredBy(models.TextChoices):
        TIME = 'time', 'Planificador (Actor Tiempo)'
        OPERATOR = 'operator', 'Corrida manual del operador'

    period = fields.Char(max_length=7, verbose_name='Periodo')  # ``YYYY-MM``
    triggered_by = fields.Selection(
        max_length=8, choices=TriggeredBy.choices, default=TriggeredBy.TIME,
        verbose_name='Disparada por',
    )
    started_at = fields.Datetime(auto_now_add=True, verbose_name='Inicio')
    finished_at = fields.Datetime(
        null=True, blank=True, verbose_name='Fin',
    )
    invoices_issued = fields.Integer(default=0, verbose_name='Facturas emitidas')
    amount_charged = fields.Monetary(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Monto cobrado',
    )
    currency = fields.Char(max_length=3, default='MXN', verbose_name='Moneda')
    failures = fields.Integer(default=0, verbose_name='Cobros fallidos')

    class Meta:
        db_table = 'subscription_billing_run'
        verbose_name = 'Corrida de facturación'
        verbose_name_plural = 'Corridas de facturación'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['period'])]

    def __str__(self):
        return f'run:{self.period}:{self.triggered_by}'


class SubscriptionInvoice(TimeStampedModel):
    """Factura recurrente de una suscripción por período (eje ``account`` L0).

    Documento de cobro **auditable** e **idempotente** por
    ``(subscription, period)`` (EX-04): reintentar una corrida no duplica la
    factura. El ``amount`` **congela** ``subscription.price`` — no referencia el
    tarifario en vivo (inmutabilidad histórica, H-API-01). El cobro reutiliza el
    eje ``payment`` del O2C (DEC-KX-07); esta factura sella el resultado en
    ``status``. Ver :ref:`diseno-motor-facturacion-recurrente-l0`.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        ISSUED = 'issued', 'Emitida'
        PAID = 'paid', 'Pagada'
        FAILED = 'failed', 'Cobro fallido'
        VOID = 'void', 'Anulada'

    company = fields.Many2one(
        Company, on_delete=models.CASCADE, related_name='subscription_invoices',
        verbose_name='Empresa',
    )
    subscription = fields.Many2one(
        CompanyModuleSubscription, on_delete=models.PROTECT,
        related_name='invoices', verbose_name='Suscripción',
    )
    run = fields.Many2one(
        SubscriptionBillingRun, on_delete=models.PROTECT, related_name='invoices',
        verbose_name='Corrida',
    )
    period = fields.Char(max_length=7, verbose_name='Periodo')  # ``YYYY-MM``
    amount = fields.Monetary(
        max_digits=10, decimal_places=2, verbose_name='Monto',
    )
    currency = fields.Char(max_length=3, default='MXN', verbose_name='Moneda')
    status = fields.Selection(
        max_length=8, choices=Status.choices, default=Status.DRAFT,
        verbose_name='Estado',
    )
    issued_at = fields.Datetime(null=True, blank=True, verbose_name='Emitida en')
    paid_at = fields.Datetime(null=True, blank=True, verbose_name='Pagada en')
    failure_reason = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Motivo de fallo',
    )

    objects = models.Manager()               # default: cross-company (L0)
    scoped = CompanyScopedManager()          # L3: fail-closed por company

    class Meta:
        db_table = 'subscription_invoice'
        verbose_name = 'Factura de suscripción'
        verbose_name_plural = 'Facturas de suscripción'
        ordering = ['-created_at']
        # Idempotencia (EX-04): una suscripción no se factura dos veces por el
        # mismo período. Reintentar la corrida es seguro.
        unique_together = [('subscription', 'period')]
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['run']),
        ]

    def __str__(self):
        return f'inv:{self.subscription_id}:{self.period}:{self.status}'
