"""CompanyModuleSubscription — módulo contratado por una company (puerta L1-a).

Parte de ``addons.sale_subscription`` — billing recurrente L0 (DEC-KX-05).
Layout ``models/`` (un archivo por modelo), espejo de odoo-tools.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
import fields
import models

from addons.base.models import TimeStampedModel
from addons.base.models import ResCompany
from orm.environments import CompanyScopedManager
from addons.sale_subscription.models.module_price import ModulePrice


class CompanyModuleSubscription(TimeStampedModel):
    """Módulo contratado por una company, con vigencia (puerta L1-a)."""

    class Status(models.TextChoices):
        TRIAL = 'trial', 'En prueba'
        ACTIVE = 'active', 'Activo'
        SUSPENDED = 'suspended', 'Suspendido'
        CANCELLED = 'cancelled', 'Cancelado'

    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, related_name='subscriptions',
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
