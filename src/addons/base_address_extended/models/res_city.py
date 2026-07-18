"""``res.city`` — ciudad de un país (Odoo ``base_address_extended``).

Portación fiel de ``res_city.py`` (18:9-22 / 19:8-21, campos idénticos; en 19 la
clase se renombró ``City`` → ``ResCity``, sólo cosmético).
"""
from django.db import models


class ResCity(models.Model):
    """``res.city`` — ciudad de un país.

    ``name`` (requerido), ``zipcode``, ``country`` FK (requerido), ``state`` FK
    (dominio país). ``__str__`` replica ``_compute_display_name`` de Odoo.
    """

    name    = models.CharField(
        max_length=120, help_text='Nombre de la ciudad (Odoo res.city.name).',
    )
    zipcode = models.CharField(
        max_length=16, blank=True, default='',
        help_text='Código postal (Odoo zipcode).',
    )
    country = models.ForeignKey(
        'base.ResCountry', on_delete=models.CASCADE, related_name='cities',
        help_text='País (Odoo country_id, requerido).',
    )
    state   = models.ForeignKey(
        'base.ResCountryState', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cities',
        help_text='Estado/provincia (Odoo state_id, dominio country_id).',
    )

    class Meta:
        db_table = 'res_city'
        ordering = ['name']
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'

    def __str__(self) -> str:
        # Fiel a _compute_display_name (o18/o19): 'name' o 'name (zipcode)'.
        return self.name if not self.zipcode else f'{self.name} ({self.zipcode})'
