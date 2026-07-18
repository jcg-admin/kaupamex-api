"""Modelos de ubicación de subcontratación — addon ``mrp_subcontracting``.

Adaptación fiel de Odoo ``mrp_subcontracting`` (verificado en 18 y 19). Las
extensiones ``_inherit`` sobre modelos de otras apps se materializan como
modelos RELATED (DEC-SALE-01) — Django no inyecta columnas cross-app.

- ``SubcontractingLocation`` — ``stock.location.is_subcontracting_location``
  (``stock_location.py:9-12``): marca una ubicación como ubicación de
  subcontratación. En Odoo debe ser ``usage='internal'`` (constraint
  ``_check_subcontracting_location``, o18:17-24) — se replica aquí.
- ``Subcontractor`` — ``res.partner.property_stock_subcontractor`` +
  ``is_subcontractor`` (``res_partner.py:6-13``): la ubicación de stock usada
  como origen/destino al enviar mercancía a ese subcontratista. El proveedor/
  partner de este proyecto es ``AUTH_USER`` (igual que ``purchase.order.partner``).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from addons.stock.models import StockLocation
from core.models import TimeStampedModel


class SubcontractingLocation(TimeStampedModel):
    """``stock.location`` marcada como ubicación de subcontratación (Odoo flag)."""

    location = models.OneToOneField(
        'stock.StockLocation', on_delete=models.CASCADE,
        related_name='subcontracting_flag',
        help_text='Ubicación base (Odoo stock.location).',
    )
    is_subcontracting_location = models.BooleanField(
        default=True,
        help_text='La ubicación es de subcontratación (Odoo '
                  'is_subcontracting_location).',
    )

    class Meta:
        db_table = 'stock_location_subcontracting'
        verbose_name = 'Ubicación de subcontratación'
        verbose_name_plural = 'Ubicaciones de subcontratación'

    def __str__(self) -> str:
        return f'subcontracting({self.location})'

    def clean(self):
        """Constraint de Odoo: la ubicación de subcontratación debe ser interna.

        Réplica de ``_check_subcontracting_location`` (o18:17-24): para valuar el
        stock con exactitud, la ubicación debe ser de tipo ``internal``.
        """
        if (self.is_subcontracting_location
                and self.location.usage != StockLocation.USAGE_INTERNAL):
            raise ValidationError(
                'Las ubicaciones de subcontratación deben ser de tipo Interna.')

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class Subcontractor(TimeStampedModel):
    """``res.partner`` subcontratista — su ubicación de stock (Odoo property_*)."""

    partner  = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='subcontractor_profile',
        help_text='Subcontratista (Odoo res.partner).',
    )
    location = models.ForeignKey(
        'stock.StockLocation', on_delete=models.PROTECT,
        related_name='subcontractors',
        help_text='Ubicación de stock del subcontratista (Odoo '
                  'property_stock_subcontractor).',
    )

    class Meta:
        db_table = 'res_partner_subcontractor'
        verbose_name = 'Subcontratista'
        verbose_name_plural = 'Subcontratistas'

    def __str__(self) -> str:
        return f'subcontractor({self.partner})'

    @property
    def is_subcontractor(self) -> bool:
        """Odoo ``res.partner.is_subcontractor`` (computado): tiene perfil."""
        return True
