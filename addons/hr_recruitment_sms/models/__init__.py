"""Modelos del addon ``hr_recruitment_sms``.

Sin modelos concretos: la única pieza (``hr_applicant.py``) es una extensión
sobre ``hr.applicant`` y NO se importa aquí — va por ``apps.py:ready()`` vía
``importlib`` (mismo patrón que ``addons/hr_skills/models/__init__.py``).
"""
