"""
Models — addons.settings_app

Tras la descomposición de la familia (H-SETTINGS-01, H-PAYMENTS-05,
H-SETTINGS-02) aquí solo queda ``ShippingMethod`` (UC-CFG-02), cuyo hogar
Odoo es ``delivery`` — pendiente de cut-over (FK-target de ``orders`` vivo).
``SiteSettings`` vive ahora en ``addons.base.models.res_config_settings``
(~ ``res.config.settings``); ``PaymentGateway`` en
``addons.payment.models.payment_provider`` (~ ``payment.provider``).
"""
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from addons.base.models import TimeStampedModel


class ShippingMethod(TimeStampedModel):
    """Método de envío disponible. UC-CFG-02."""
    name           = models.CharField(max_length=100)
    cost           = models.DecimalField(
                       max_digits=10, decimal_places=2,
                       validators=[MinValueValidator(Decimal('0'))],
                       help_text='Costo de envío. 0 = gratis.')
    estimated_days = models.PositiveSmallIntegerField()
    is_active      = models.BooleanField(default=True, db_index=True)
    free_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    zones          = models.JSONField(default=list, blank=True)

    class Meta:
        db_table     = 'settings_shipping_method'
        ordering     = ['cost', 'name']
        verbose_name = 'Método de envío'

    def __str__(self):
        return f'{self.name} (${self.cost})'
