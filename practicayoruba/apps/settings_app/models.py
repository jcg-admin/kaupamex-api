"""
SiteSettings — UC-CFG-03
Singleton de configuración global del sistema.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default='PracticaYoruba')
    iva_rate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0.16'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('1.00'))],
    )
    currency = models.CharField(max_length=3, default='MXN')
    order_timeout_minutes = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1)]
    )
    max_return_days = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1)]
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('500.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'settings_sitesettings'
        verbose_name = 'Configuracion del sitio'

    def __str__(self):
        return f'SiteSettings — {self.site_name} (IVA {float(self.iva_rate):.0%})'

    def clean(self):
        if self.currency and len(self.currency) != 3:
            raise ValidationError({'currency': 'Debe tener 3 caracteres.'})
        if self.iva_rate is not None:
            if self.iva_rate < Decimal('0.00') or self.iva_rate > Decimal('1.00'):
                raise ValidationError({'iva_rate': 'Debe estar entre 0.00 y 1.00.'})
        if self.free_shipping_threshold is not None and self.free_shipping_threshold < 0:
            raise ValidationError({'free_shipping_threshold': 'No puede ser negativo.'})
        if self.order_timeout_minutes is not None and self.order_timeout_minutes < 1:
            raise ValidationError({'order_timeout_minutes': 'Debe ser >= 1 minuto.'})

    def save(self, *args, **kwargs):
        if not self.pk and SiteSettings.objects.exists():
            raise ValidationError('SiteSettings es un singleton.')
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_defaults(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def get_current(cls):
        return cls.get_or_create_defaults()
