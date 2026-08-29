"""Modelo ``CrmLostReason`` — addon ``crm``.

Adaptación fiel de Odoo ``crm/models/crm_lost_reason.py``
(``crm.lost.reason``): motivo por el que una oportunidad se pierde. Se portan
los tres campos y los dos métodos que la referencia declara.
"""
from django.db.models import Count
import fields
import models

from addons.base.models import TimeStampedModel
from tools.translate import _


class CrmLostReason(TimeStampedModel):
    """``crm.lost.reason`` — motivo de pérdida de una oportunidad."""

    _name = 'crm.lost.reason'
    _description = 'Opp. Lost Reason'

    # Odoo name (crm_lost_reason.py:11, required, translate).
    name   = fields.Char(
        max_length=255, help_text='Descripción del motivo (Odoo name).',
    )
    # Odoo active (crm_lost_reason.py:12, default True).
    active = fields.Boolean(
        default=True, help_text='Archivar sin borrar (Odoo active).',
    )

    class Meta:
        db_table = 'crm_lost_reason'
        ordering = ['id']
        verbose_name = 'Motivo de pérdida'
        verbose_name_plural = 'Motivos de pérdida'

    def __str__(self) -> str:
        return self.name

    # Odoo leads_count (crm_lost_reason.py:13, compute='_compute_leads_count').
    # Calculado, no persistido: por eso es property y no columna.
    @property
    def leads_count(self):
        """≙ el campo calculado ``leads_count``."""
        return type(self)._compute_leads_count([self])[self.pk]

    @classmethod
    def _compute_leads_count(cls, reasons):
        """≙ ``_compute_leads_count`` (crm_lost_reason.py:15-23).

        La referencia agrupa con ``_read_group`` sobre ``crm.lead`` **con
        ``active_test=False``**: cuenta también las oportunidades archivadas,
        que es justo la población que interesa a un motivo de pérdida. Aquí el
        agrupamiento es un ``values().annotate()``, y el ``active_test=False``
        se expresa no filtrando por ``active``.
        """
        ids = [r.pk for r in reasons]
        # La fuente resuelve por nombre (``self.env['crm.lead']``) y por eso
        # no tiene ciclo. Aquí el equivalente es el registro de Django: es
        # una LLAMADA, no un statement ``import``, así que respeta
        # no-lazy-imports (misma resolución sancionada que su excepción #4)
        # y rompe el ciclo real crm_lost_reason -> crm_lead -> crm_lost_reason.
        CrmLead = models.apps.get_model('crm', 'CrmLead')
        grouped = dict(CrmLead.objects.filter(lost_reason_id__in=ids)
                     .values_list('lost_reason_id')
                     .annotate(n=Count('pk')))
        return {i: grouped.get(i, 0) for i in ids}

    def action_lost_leads(self):
        """≙ ``action_lost_leads`` (crm_lost_reason.py:25-33).

        Devuelve el ``ir.actions.act_window`` que abre las oportunidades
        perdidas por este motivo, con ``create`` desactivado y
        ``active_test=False`` para incluir las archivadas.
        """
        return {
            'name': _('Iniciativas'),
            'view_mode': 'list,form',
            'domain': [('lost_reason_id', 'in', [self.pk])],
            'res_model': 'crm.lead',
            'type': 'ir.actions.act_window',
            'context': {'create': False, 'active_test': False},
        }
