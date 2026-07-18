"""Modelo ``CrmTag`` — addon ``sales_team``.

Adaptación fiel de ``sales_team/models/crm_tag.py`` (``crm.tag``): etiqueta
reutilizable para clasificar oportunidades/órdenes. ``sale.order`` la referencia
vía ``tag_ids`` (Many2many). Núcleo: ``name`` único + ``color``.
"""
from django.db import models

from core.models import TimeStampedModel


class CrmTag(TimeStampedModel):
    """``crm.tag`` — etiqueta de CRM/ventas."""

    # Odoo crm.tag.name (crm_tag.py:15, required, translate, unique).
    name  = models.CharField(
        max_length=100, unique=True,
        help_text='Nombre de la etiqueta (Odoo crm.tag.name).',
    )
    # Odoo color (crm_tag.py:16).
    color = models.IntegerField(
        default=0, help_text='Índice de color (Odoo crm.tag.color).',
    )

    class Meta:
        db_table = 'crm_tag'
        ordering = ['name']
        verbose_name = 'Etiqueta de venta'
        verbose_name_plural = 'Etiquetas de venta'

    def __str__(self) -> str:
        return self.name
