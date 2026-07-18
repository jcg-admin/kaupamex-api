"""Modelo ``CrmTeamMember`` — addon ``sales_team``.

Adaptación fiel de ``sales_team/models/crm_team_member.py`` (``crm.team.member``):
tabla intermedia explícita entre ``crm.team`` y ``res.users`` que materializa la
membresía ``member_ids``. Odoo la usa como through model para poder archivar una
membresía (``active``) sin retirar al usuario, y para colgar de ella campos de
CRM (metas, dashboard). Aquí se porta el núcleo relacional.
"""
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class CrmTeamMember(TimeStampedModel):
    """``crm.team.member`` — membresía usuario↔equipo."""

    # Odoo crm_team_id (crm_team_member.py:14, required, ondelete cascade).
    crm_team = models.ForeignKey(
        'sales_team.CrmTeam', on_delete=models.CASCADE,
        related_name='member_links',
        help_text='Equipo (Odoo crm.team.member.crm_team_id).',
    )
    # Odoo user_id (crm_team_member.py:19, required).
    user     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sales_team_memberships',
        help_text='Vendedor (Odoo crm.team.member.user_id).',
    )
    # Odoo active (crm_team_member.py:29) — archivar la membresía.
    active   = models.BooleanField(
        default=True,
        help_text='Archivar la membresía sin borrarla (Odoo active).',
    )

    class Meta:
        db_table = 'crm_team_member'
        # Odoo _sql_constraints: un usuario no se repite activo en un equipo.
        constraints = [
            models.UniqueConstraint(
                fields=['crm_team', 'user'], name='uniq_crm_team_member',
            ),
        ]
        verbose_name = 'Miembro de equipo de venta'
        verbose_name_plural = 'Miembros de equipo de venta'

    def __str__(self) -> str:
        return f'{self.user} @ {self.crm_team}'
