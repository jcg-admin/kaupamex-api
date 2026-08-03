"""Subsidiary — entidad legal bajo la Company (jerarquía OneWorld).

Parte de ``addons.platform`` — capa L1 de la plataforma Kaupamex.
Layout ``models/`` (un archivo por modelo), espejo de odoo-tools.
"""

import fields
import models

from addons.base.models import TimeStampedModel, _reject_hierarchy_cycle
from addons.platform.models.company import Company


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
