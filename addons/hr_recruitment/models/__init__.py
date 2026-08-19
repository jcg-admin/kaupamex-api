"""Modelos concretos del addon ``hr_recruitment`` (estructura Odoo: un
addon, un archivo por modelo).

Sólo los modelos con ``_name`` propio se importan aquí — las extensiones
(``res_company.py``, ``res_partner.py``, ``res_users.py``, ``ir_attachment.py``,
``ir_ui_menu.py``, ``utm_campaign.py``, ``utm_source.py``, ``digest.py``,
``calendar.py``, ``mail_activity_plan.py``, ``hr_job.py``,
``hr_department.py``, ``hr_employee.py``, ``res_config_settings.py``) se
aplican tarde desde ``HrRecruitmentConfig.ready()`` (registro de modelos
aún no poblado en tiempo de import de este paquete).
"""
from .hr_applicant import HrApplicant
from .hr_applicant_category import HrApplicantCategory
from .hr_applicant_refuse_reason import HrApplicantRefuseReason
from .hr_job_platform import HrJobPlatform
from .hr_recruitment_degree import HrRecruitmentDegree
from .hr_recruitment_source import HrRecruitmentSource
from .hr_recruitment_stage import HrRecruitmentStage
from .hr_talent_pool import HrTalentPool

__all__ = [
    'HrApplicant', 'HrApplicantCategory', 'HrApplicantRefuseReason',
    'HrJobPlatform', 'HrRecruitmentDegree', 'HrRecruitmentSource',
    'HrRecruitmentStage', 'HrTalentPool',
]
