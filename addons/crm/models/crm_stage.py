"""Modelo ``CrmStage`` — addon ``crm``.

Adaptación fiel de Odoo ``crm/models/crm_stage.py`` (``crm.stage``): etapa del
pipeline de oportunidades. Se portan los diez campos y los tres métodos que la
referencia declara (``odoo19c: crm/models/crm_stage.py``), más su constante de
módulo ``AVAILABLE_PRIORITIES``.
"""
import api
import fields
import models

from addons.base.models import TimeStampedModel
from addons.sales_team.models import CrmTeam
from tools.translate import _

# ≙ ``AVAILABLE_PRIORITIES`` (crm_stage.py:6-11). La consume ``crm.lead.priority``.
AVAILABLE_PRIORITIES = [
    ('0', 'Baja'),
    ('1', 'Media'),
    ('2', 'Alta'),
    ('3', 'Muy alta'),
]


class CrmStage(TimeStampedModel):
    """``crm.stage`` — etapa del pipeline de oportunidades.

    Modela las etapas principales de un flujo de gestión documental. Los objetos
    CRM (iniciativas, oportunidades) usan sólo etapas, no un estado aparte.
    """

    _name = 'crm.stage'
    _description = "CRM Stages"
    _rec_name = 'name'
    _order = "sequence, name, id"

    # Odoo crm.stage.name (crm_stage.py:25, required, translate).
    name                   = fields.Char(
        max_length=100, help_text='Nombre de la etapa (Odoo crm.stage.name).',
    )
    # Odoo sequence (crm_stage.py:26, default 1 — menor es mejor).
    sequence               = fields.Integer(
        default=1, help_text='Orden del pipeline; menor primero (Odoo sequence).',
    )
    # Odoo is_won (crm_stage.py:27) — etapa ganada.
    is_won                 = fields.Boolean(
        default=False, help_text='Etapa ganada (Odoo is_won).',
    )
    # Odoo rotting_threshold_days (crm_stage.py:28, default 0 — 0 desactiva).
    rotting_threshold_days = fields.Integer(
        default=0,
        help_text='Días sin actualizar tras los que la oportunidad se resalta; '
                  '0 desactiva (Odoo rotting_threshold_days).',
    )
    # Odoo requirements (crm_stage.py:30) — tooltip sobre el nombre de la etapa.
    requirements           = fields.Text(
        blank=True, default='',
        help_text='Requisitos internos de la etapa (Odoo requirements).',
    )
    # Odoo team_ids (crm_stage.py:31, ondelete restrict).
    team_ids               = fields.Many2many(
        'sales_team.CrmTeam', blank=True, related_name='crm_stages',
        help_text='Equipos de venta que usan la etapa (Odoo team_ids).',
    )
    # Odoo fold (crm_stage.py:32) — plegada en el kanban.
    fold                   = fields.Boolean(
        default=False, help_text='Plegada en el pipeline (Odoo fold).',
    )
    # Odoo color (crm_stage.py:36).
    color                  = fields.Integer(
        default=0, help_text='Índice de color (Odoo color).',
    )

    class Meta:
        db_table = 'crm_stage'
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Etapa de CRM'
        verbose_name_plural = 'Etapas de CRM'

    def __str__(self) -> str:
        return self.name

    # Odoo team_count (crm_stage.py:34, compute='_compute_team_count'). Campo de
    # interfaz: no se persiste, por eso es una property y no una columna.
    @property
    def team_count(self):
        """≙ el campo calculado ``team_count``."""
        return self._compute_team_count()

    @api.depends('team_ids')
    def _compute_team_count(self):
        """≙ ``_compute_team_count`` (crm_stage.py:39-41).

        La referencia cuenta TODOS los equipos, no los de la etapa: es el total
        del sistema, que la vista usa para decidir si muestra el selector de
        equipo. Se porta con esa semántica, no con la que el nombre sugiere.
        """
        return CrmTeam.objects.count()

    @api.onchange('is_won')
    def _onchange_is_won(self):
        """≙ ``_onchange_is_won`` (crm_stage.py:43-51).

        Devuelve el aviso que la referencia muestra antes de guardar: marcar la
        etapa como ganada recalcula la probabilidad de todas sus oportunidades.
        """
        return {
            'warning': {
                'title': _("¿Realmente quieres actualizar esta etapa?"),
                'message': _(
                    "Cambiar el valor de «Etapa ganada» puede inducir un número "
                    "grande de operaciones: las probabilidades de las "
                    "oportunidades de esta etapa se recalculan al guardar."),
            }
        }

    def save(self, *args, **kwargs):
        """≙ el ``write`` de la referencia (crm_stage.py:53-68).

        Una oportunidad en etapa ganada tiene probabilidad 100 %. Al marcar la
        etapa como ganada se fija en 100 la de todas sus oportunidades; al
        desmarcarla se recalcula desde la probabilidad automática.

        En Django el punto de escritura es ``save()``, no ``write()``: hay que
        leer el valor anterior ANTES de delegar, porque después la fila ya trae
        el nuevo. La referencia lo resuelve mirando ``'is_won' in vals``.
        """
        previous = None
        if self.pk:
            previous = (type(self).objects.filter(pk=self.pk)
                      .values_list('is_won', flat=True).first())
        res = super().save(*args, **kwargs)
        if previous is not None and previous != self.is_won:
            # La fuente resuelve por nombre (``self.env['crm.lead']``,
            # crm_stage.py:62) y por eso no tiene ciclo. Aquí el
            # equivalente es el registro de Django: es una LLAMADA, no un
            # statement ``import``, así que respeta no-lazy-imports (misma
            # resolución sancionada que su excepción #4) y rompe el ciclo
            # real crm_stage -> crm_lead -> crm_stage.
            CrmLead = models.apps.get_model('crm', 'CrmLead')
            won_leads = CrmLead.objects.filter(stage_id=self.pk)
            if self.is_won:
                won_leads.update(probability=100, automated_probability=100)
            else:
                for lead in won_leads:
                    lead._compute_probabilities()
        return res
