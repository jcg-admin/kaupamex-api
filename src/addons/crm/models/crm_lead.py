"""Modelo ``CrmLead`` — addon ``crm``.

Adaptación fiel de Odoo ``crm/models/crm_lead.py`` (``crm.lead``): iniciativa u
oportunidad de venta. Se portan los campos comerciales core; el scoring
predictivo, recurrencia y actividades de Odoo quedan fuera (requieren módulos
adicionales).
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class CrmLead(TimeStampedModel):
    """``crm.lead`` — iniciativa/oportunidad de venta."""

    # Odoo type (crm_lead.py:123): lead (iniciativa) vs opportunity (oportunidad).
    TYPE_LEAD        = 'lead'
    TYPE_OPPORTUNITY = 'opportunity'
    TYPES = [
        (TYPE_LEAD, 'Iniciativa'),
        (TYPE_OPPORTUNITY, 'Oportunidad'),
    ]
    # Odoo priority (crm_lead.py:127).
    PRIORITIES = [('0', 'Baja'), ('1', 'Media'), ('2', 'Alta'), ('3', 'Muy alta')]

    name             = models.CharField(
        max_length=255, help_text='Nombre de la oportunidad (Odoo crm.lead.name).',
    )
    type             = models.CharField(
        max_length=12, choices=TYPES, default=TYPE_LEAD,
        help_text='Iniciativa u oportunidad (Odoo type).',
    )
    priority         = models.CharField(
        max_length=1, choices=PRIORITIES, default='0',
        help_text='Prioridad (Odoo priority).',
    )
    active           = models.BooleanField(
        default=True, help_text='Archivar sin borrar (Odoo active).',
    )
    description      = models.TextField(
        blank=True, default='', help_text='Notas (Odoo description).',
    )
    stage            = models.ForeignKey(
        'crm.CrmStage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='leads', help_text='Etapa del pipeline (Odoo stage_id).',
    )
    expected_revenue = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Ingreso esperado (Odoo expected_revenue).',
    )
    probability      = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Probabilidad % (Odoo probability).',
    )
    partner          = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads', help_text='Cliente asociado (Odoo partner_id).',
    )
    contact_name     = models.CharField(
        max_length=150, blank=True, default='',
        help_text='Nombre de contacto (Odoo contact_name).',
    )
    email_from       = models.EmailField(
        null=True, blank=True, help_text='Correo (Odoo email_from).',
    )
    phone            = models.CharField(
        max_length=30, blank=True, default='', help_text='Teléfono (Odoo phone).',
    )
    user             = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads_owned', help_text='Vendedor (Odoo user_id).',
    )
    team             = models.ForeignKey(
        'sales_team.CrmTeam', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crm_leads', help_text='Equipo de venta (Odoo team_id).',
    )

    class Meta:
        db_table = 'crm_lead'
        ordering = ['-priority', '-created_at']
        verbose_name = 'Oportunidad de CRM'
        verbose_name_plural = 'Oportunidades de CRM'

    def __str__(self) -> str:
        return self.name
