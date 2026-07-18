"""Vínculo BoM ↔ subcontratista + subcontratista de la orden — ``mrp_subcontracting``.

Adaptación fiel de Odoo ``mrp_subcontracting`` (verificado en 18 y 19). Las
extensiones ``_inherit`` cross-app se materializan como modelos RELATED
(DEC-SALE-01).

- ``BomSubcontractor`` — ``mrp.bom.subcontractor_ids`` (M2M ``mrp_bom_subcontractor``,
  ``mrp_bom.py:14``): qué subcontratistas pueden fabricar esa BoM. Se materializa
  como tabla puente explícita (Django no inyecta el M2M en ``mrp.MrpBom``); el
  ``db_table`` conserva el nombre canónico de Odoo ``mrp_bom_subcontractor``.
- ``SubcontractProduction`` — ``mrp.production.subcontractor_id``
  (``mrp_production.py:20``): el subcontratista que fabrica la orden. El partner/
  proveedor del proyecto es ``AUTH_USER`` (igual que ``purchase.order.partner``).
"""
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class BomSubcontractor(TimeStampedModel):
    """``mrp.bom.subcontractor_ids`` — puente BoM ↔ subcontratista (M2M Odoo)."""

    bom          = models.ForeignKey(
        'mrp.MrpBom', on_delete=models.CASCADE, related_name='subcontractor_links',
        help_text='BoM de subcontratación (Odoo mrp.bom).',
    )
    subcontractor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='subcontracted_boms',
        help_text='Subcontratista (Odoo res.partner).',
    )

    class Meta:
        db_table = 'mrp_bom_subcontractor'
        constraints = [
            models.UniqueConstraint(
                fields=['bom', 'subcontractor'], name='unique_bom_subcontractor',
            ),
        ]
        verbose_name = 'Subcontratista de BoM'
        verbose_name_plural = 'Subcontratistas de BoM'

    def __str__(self) -> str:
        return f'{self.bom} ← {self.subcontractor}'


class SubcontractProduction(TimeStampedModel):
    """``mrp.production.subcontractor_id`` — subcontratista de la orden (Odoo)."""

    production   = models.OneToOneField(
        'mrp.MrpProduction', on_delete=models.CASCADE,
        related_name='subcontract',
        help_text='Orden de fabricación (Odoo mrp.production).',
    )
    subcontractor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name='subcontract_productions',
        help_text='Subcontratista de la orden (Odoo subcontractor_id).',
    )

    class Meta:
        db_table = 'mrp_production_subcontractor'
        verbose_name = 'Subcontratación de orden'
        verbose_name_plural = 'Subcontrataciones de orden'

    def __str__(self) -> str:
        return f'{self.production} ← {self.subcontractor}'
