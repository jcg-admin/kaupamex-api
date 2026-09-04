"""Modelos del addon ``crm`` (estructura Odoo: un archivo por modelo)."""
from .crm_lead import CrmLead
from .crm_lead_scoring_frequency import (
    CrmLeadScoringFrequency,
    CrmLeadScoringFrequencyField,
)
from .crm_lost_reason import CrmLostReason
from .crm_recurring_plan import CrmRecurringPlan
from .crm_stage import CrmStage
from .contact_message import ContactMessage

__all__ = [
    'CrmLead', 'CrmLeadScoringFrequency', 'CrmLeadScoringFrequencyField',
    'CrmLostReason', 'CrmRecurringPlan', 'CrmStage', 'ContactMessage',
]
