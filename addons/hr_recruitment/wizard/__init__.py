"""Wizards del addon ``hr_recruitment`` — espejo de ``odoo19c: hr_recruitment/
wizard/``.

``mail_activity_schedule`` no se importa aquí: su extensión es un no-op
declarado, aplicado tarde desde ``HrRecruitmentConfig.ready()`` (el modelo
destino no existe — ver su propio docstring).
"""
from .applicant_refuse_reason import ApplicantGetRefuseReason
from .applicant_send_mail import ApplicantSendMail
from .job_add_applicants import JobAddApplicants
from .talent_pool_add_applicants import TalentPoolAddApplicants

__all__ = [
    'ApplicantGetRefuseReason', 'ApplicantSendMail', 'JobAddApplicants',
    'TalentPoolAddApplicants',
]
