"""Modelo ``CrmTeamMember`` — addon ``sales_team``.

Adaptación fiel de ``sales_team/models/crm_team_member.py`` (``crm.team.member``):
tabla intermedia explícita entre ``crm.team`` y ``res.users`` que materializa la
membresía ``member_ids``. Odoo la usa como through model para poder archivar una
membresía (``active``) sin retirar al usuario, y para colgar de ella campos de
CRM (metas, dashboard). Aquí se porta el núcleo relacional.
"""
from django.conf import settings
import fields
import models

from addons.base.models import TimeStampedModel


class CrmTeamMember(TimeStampedModel):
    """``crm.team.member`` — membresía usuario↔equipo."""

    _name = 'crm.team.member'
    _description = 'Sales Team Member'
    _inherit = ['mail.thread']
    _rec_name = 'user_id'
    _order = 'create_date ASC, id'

    # Odoo crm_team_id (crm_team_member.py:14, required, ondelete cascade).
    crm_team_id = fields.Many2one(
        'sales_team.CrmTeam', on_delete=models.CASCADE,
        # ≙ ``crm_team_member_ids`` (odoo19c: sales_team/models/crm_team.py:107),
        # el One2many con que el equipo nombra a sus membresías. El nombre lo
        # fija la referencia; ``member_links`` era invención de este árbol.
        related_name='crm_team_member_ids',
        help_text='Equipo (Odoo crm.team.member.crm_team_id).',
        db_column='crm_team_id',
    )
    # Odoo user_id (crm_team_member.py:19, required).
    user_id  = fields.Many2one(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sales_team_memberships',
        help_text='Vendedor (Odoo crm.team.member.user_id).',
        db_column='user_id',
    )
    # Odoo active (crm_team_member.py:29) — archivar la membresía.
    active   = fields.Boolean(
        default=True,
        help_text='Archivar la membresía sin borrarla (Odoo active).',
    )

    class Meta:
        db_table = 'crm_team_member'
        # Odoo _sql_constraints: un usuario no se repite activo en un equipo.
        constraints = [
            models.UniqueConstraint(
                fields=['crm_team_id', 'user_id'], name='uniq_crm_team_member',
            ),
        ]
        verbose_name = 'Miembro de equipo de venta'
        verbose_name_plural = 'Miembros de equipo de venta'

    def __str__(self) -> str:
        return f'{self.user_id} @ {self.crm_team_id}'
