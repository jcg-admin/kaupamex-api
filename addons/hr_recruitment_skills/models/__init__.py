"""Modelos del addon ``hr_recruitment_skills`` (estructura Odoo: un archivo
por modelo).

Sólo se importa aquí el modelo concreto. Las DOS extensiones de este addon
sobre modelos ajenos (``hr.applicant`` en ``hr_applicant.py``, ``hr.job`` en
``hr_job.py``) NO se importan: van por ``apps.py:ready()`` vía ``importlib``
(mismo patrón que ``addons/hr_skills/models/__init__.py``).
"""
from .hr_applicant_skill import HrApplicantSkill

__all__ = ['HrApplicantSkill']
