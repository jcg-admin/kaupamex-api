"""ModulePrice — tarifario por Module x ciclo, con vigencia (DEC-T6).

Parte de ``addons.sale_subscription`` — billing recurrente L0 (DEC-KX-05).
Layout ``models/`` (un archivo por modelo), espejo de odoo-tools.
"""

from django.utils import timezone
import fields
import models

from addons.base.models import TimeStampedModel


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
