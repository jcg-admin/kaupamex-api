"""``res.country.group`` — grupos de países (Odoo ``base``).

Portación fiel de ``ResCountryGroup`` (``res_country.py`` de Odoo 18/19).
Agrupa países (p. ej. Unión Europea, NAFTA) para reglas fiscales/logísticas.
M2M a ``base.ResCountry``.
"""
from django.db import models


class ResCountryGroup(models.Model):
    """``res.country.group`` — conjunto nombrado de países."""

    name        = models.CharField(max_length=128, help_text='Nombre del grupo (Odoo name).')
    code        = models.CharField(
        max_length=16, blank=True, default='', help_text='Código del grupo (Odoo code).',
    )
    country_ids = models.ManyToManyField(
        'base.ResCountry', related_name='country_groups', blank=True,
        db_table='res_country_res_country_group_rel',
        help_text='Países del grupo (Odoo country_ids).',
    )

    class Meta:
        db_table = 'res_country_group'
        ordering = ['name']
        verbose_name = 'Grupo de países'
        verbose_name_plural = 'Grupos de países'

    def __str__(self) -> str:
        return self.name
