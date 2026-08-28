"""Modelos de la tabla de frecuencias del scoring predictivo — addon ``crm``.

Adaptación fiel de ``crm/models/crm_lead_scoring_frequency.py``. Son las dos
piezas del *predictive lead scoring*: la tabla de frecuencias que alimenta al
clasificador bayesiano ingenuo de ``CrmLead._pls_get_naive_bayes_probabilities``
y el catálogo de campos que la configuración admite como variable.
"""
from random import randint

import fields
import models

from addons.base.models import TimeStampedModel
from addons.base.models.ir_model import IrModelFields
from addons.sales_team.models import CrmTeam


class CrmLeadScoringFrequency(TimeStampedModel):
    """``crm.lead.scoring.frequency`` — una fila por (variable, valor, equipo)."""

    _name = 'crm.lead.scoring.frequency'
    _description = 'Lead Scoring Frequency'

    # Odoo variable (crm_lead_scoring_frequency.py:12, index=True).
    variable   = fields.Char(
        max_length=255, db_index=True, blank=True, default='',
        help_text='Nombre del campo de crm.lead que actúa como variable.',
    )
    # Odoo value (:13).
    value      = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Valor de la variable, siempre como texto.',
    )
    # Odoo won_count / lost_count (:14-15, Float con digits=(16, 1)).
    #
    # El tipo es Float en la fuente **a propósito**: el algoritmo suma 0.1 a
    # cada cuenta para esquivar la frecuencia cero. `digits` allá es precisión
    # de presentación y el FloatField de Django no la declara — divergencia de
    # mecanismo, no omisión: el valor almacenado es el mismo.
    won_count  = fields.Float(default=0.0, help_text='Veces ganadas (Odoo won_count).')
    lost_count = fields.Float(default=0.0, help_text='Veces perdidas (Odoo lost_count).')
    # Odoo team_id (:16, ondelete="cascade").
    team_id    = fields.Many2one(
        CrmTeam, null=True, blank=True, on_delete=models.CASCADE,
        related_name='lead_scoring_frequencies', db_column='team_id',
        help_text='Equipo de venta dueño de la frecuencia (Odoo team_id).',
    )

    class Meta:
        db_table = 'crm_lead_scoring_frequency'
        verbose_name = 'Frecuencia de scoring'
        verbose_name_plural = 'Frecuencias de scoring'

    def __str__(self) -> str:
        return f'{self.variable}={self.value}'


class CrmLeadScoringFrequencyField(TimeStampedModel):
    """``crm.lead.scoring.frequency.field`` — campo admitido como variable."""

    _name = 'crm.lead.scoring.frequency.field'
    _description = 'Fields that can be used for predictive lead scoring computation'

    def _get_default_color():
        """≙ ``_get_default_color`` (crm_lead_scoring_frequency.py:22-23).

        Se declara DENTRO de la clase, donde la fuente lo declara. Sin ``self``:
        el ``default`` de Django resuelve sin instancia, y en el cuerpo de la
        clase el nombre todavía es una función suelta cuando el campo lo toma.
        Mismo rango, 1 a 11 inclusive.
        """
        return randint(1, 11)

    # Odoo name (crm_lead_scoring_frequency.py:26, related="field_id.field_description").
    #
    # `related=` de la fuente es un campo espejo almacenado; aquí se deriva en
    # lectura desde la FK, que es lo que Django ofrece sin duplicar la columna.
    @property
    def name(self):
        """≙ el ``related`` de ``field_id.field_description``."""
        return self.field_id.field_description if self.field_id_id else ''

    # Odoo field_id (:27-30, required, ondelete='cascade',
    # domain=[('model_id.model', '=', 'crm.lead')]).
    field_id = fields.Many2one(
        IrModelFields, on_delete=models.CASCADE,
        related_name='crm_lead_scoring_uses', db_column='field_id',
        help_text='Campo de crm.lead usado como variable (Odoo field_id).',
    )
    # Odoo color (:31).
    color    = fields.Integer(
        default=_get_default_color, help_text='Índice de color (Odoo color).',
    )

    class Meta:
        db_table = 'crm_lead_scoring_frequency_field'
        verbose_name = 'Campo de scoring'
        verbose_name_plural = 'Campos de scoring'

    def __str__(self) -> str:
        return self.name or ''
