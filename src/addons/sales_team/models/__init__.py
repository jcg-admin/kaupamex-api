"""Modelos del addon ``sales_team`` (estructura Odoo: un archivo por modelo)."""
from .crm_tag import CrmTag
from .crm_team import CrmTeam
from .crm_team_member import CrmTeamMember

__all__ = ['CrmTag', 'CrmTeam', 'CrmTeamMember']
