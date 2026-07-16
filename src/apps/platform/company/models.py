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
    # Placeholder de facturación — el modelo de precios sigue abierto (diseño).
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
