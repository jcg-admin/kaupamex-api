"""``fleet.service.type`` — catálogo de tipos de servicio/contrato (Odoo ``fleet``).

Adaptación fiel de Odoo fleet/models/fleet_service_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import fields

from addons.base.models import TimeStampedModel


class FleetServiceType(TimeStampedModel):
    """``fleet.service.type`` — tipo de costo: contrato, servicio, o ambos."""

    CATEGORY_CONTRACT = 'contract'
    CATEGORY_SERVICE = 'service'
    CATEGORIES = [
        (CATEGORY_CONTRACT, 'Contrato'),
        (CATEGORY_SERVICE, 'Servicio'),
    ]

    name = fields.Char(
        max_length=150,
        help_text='Nombre del tipo de servicio (Odoo name, translate=True '
                   'en la referencia; i18n no portado).',
    )
    category = fields.Selection(
        max_length=10, choices=CATEGORIES,
        help_text='Si el tipo aplica a contratos, a servicios, o a ambos '
                   '(Odoo category).',
    )

    class Meta:
        db_table = 'fleet_service_type'
        ordering = ['name']
        verbose_name = 'Tipo de servicio de flota'
        verbose_name_plural = 'Tipos de servicio de flota'

    def __str__(self):
        return self.name or ''
