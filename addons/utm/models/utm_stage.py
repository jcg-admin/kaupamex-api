"""``utm.stage`` — la etapa de una campaña UTM.

Adaptación fiel de Odoo ``utm/models/utm_stage.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). La fuente declara **0 métodos**: es sólo dos campos y
su orden. Se porta tal cual.
"""
import fields
import models
from addons.base.models import TimeStampedModel


class UtmStage(TimeStampedModel):
    """``utm.stage`` — etapa de campaña (``odoo19c: utm_stage.py:8-16``)."""

    _name = 'utm.stage'
    _description = 'Campaign Stage'
    _order = 'sequence'

    # ≙ ``name`` (requerido, traducible en la referencia).
    name = fields.Char(
        max_length=255, verbose_name='Nombre',
        help_text='Nombre de la etapa.',
    )
    # ≙ ``sequence``.
    sequence = fields.Integer(
        default=1, verbose_name='Secuencia',
        help_text='Orden de presentación.',
    )

    class Meta:
        db_table = 'utm_stage'
        # ≙ ``_order = 'sequence'`` (``odoo19c: :13``).
        ordering = ['sequence']
        verbose_name = 'Etapa de campaña'
        verbose_name_plural = 'Etapas de campaña'

    def __str__(self) -> str:
        return self.name
