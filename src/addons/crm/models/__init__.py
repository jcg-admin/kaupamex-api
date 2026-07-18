"""Modelos del addon ``crm`` (estructura Odoo: un archivo por modelo)."""
from .crm_lead import CrmLead
from .crm_stage import CrmStage

__all__ = ['CrmLead', 'CrmStage']
