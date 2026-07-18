"""Modelo ``CrmTeam`` — addon ``sales_team``.

Adaptación fiel del módulo Odoo ``sales_team`` (``sales_team/models/crm_team.py``).
En Odoo ``sale.order.team_id`` (Many2one a ``crm.team``) atribuye cada orden a un
equipo de venta; ``sale`` declara ``sales_team`` como dependencia. Este addon
provee el modelo canónico ``crm.team`` para esa atribución.

Fidelidad de scope: se portan los campos comerciales core del equipo
(``name``/``sequence``/``active``/``company``/``user_id`` líder/``color`` +
membresías vía ``crm.team.member``). Los campos de dashboard/CRM-pipeline
(``use_leads``, ``opportunities_count``, ``invoiced``) NO viven aquí — en Odoo
los añaden ``crm`` y ``sale`` sobre el modelo base; se integran en esos addons.
"""
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class CrmTeam(TimeStampedModel):
    """``crm.team`` — equipo de venta (Sales Team)."""

    # Odoo crm.team.name (crm_team.py:85, required, translate).
    name        = models.CharField(
        max_length=150, help_text='Nombre del equipo (Odoo crm.team.name).',
    )
    # Odoo sequence (crm_team.py:86, default 10) — orden de listado.
    sequence    = models.IntegerField(
        default=10, help_text='Orden de listado (Odoo crm.team.sequence).',
    )
    # Odoo active (crm_team.py:87) — archivar sin borrar.
    active      = models.BooleanField(
        default=True,
        help_text='Archivar el equipo sin borrarlo (Odoo crm.team.active).',
    )
    # Odoo company_id — equipo por Company (L1 tenant). Multi-company.
    company     = models.ForeignKey(
        'company.Company', null=True, blank=True,
        on_delete=models.CASCADE, related_name='sales_teams',
        help_text='Company propietaria (Odoo crm.team.company_id).',
    )
    # Odoo user_id (crm_team.py:93) — líder del equipo (Team Leader).
    leader      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='led_sales_teams',
        help_text='Líder del equipo (Odoo crm.team.user_id).',
    )
    # Odoo member_ids (crm_team.py:98) — Many2many a res.users vía la
    # tabla intermedia crm.team.member (through model explícito, como Odoo).
    members     = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='sales_team.CrmTeamMember',
        related_name='sales_teams', blank=True,
        help_text='Vendedores del equipo (Odoo crm.team.member_ids).',
    )
    # Odoo color (crm_team.py:115) — índice de color en el kanban.
    color       = models.IntegerField(
        default=0, help_text='Índice de color (Odoo crm.team.color).',
    )

    class Meta:
        db_table = 'crm_team'
        # Odoo _order = "sequence ASC, create_date DESC, id DESC".
        ordering = ['sequence', '-created_at', '-id']
        verbose_name = 'Equipo de venta'
        verbose_name_plural = 'Equipos de venta'

    def __str__(self) -> str:
        return self.name
