"""AppConfig — addons.hr_recruitment (equivalente del addon ``hr_recruitment``
de Odoo).

Mismo patrón que ``addons.hr``/``addons.account``: los modelos concretos se
importan en ``models/__init__.py``; lo que este addon cuelga sobre modelos
AJENOS (``hr.HrJob``, ``hr.HrDepartment``, ``base.ResCompany``,
``base.ResUsers``, ``base.IrAttachment``, ``base.IrUiMenu``,
``utm.UtmCampaign``/``UtmSource``, ``digest.DigestDigest``) se aplica tarde
desde ``ready()`` — en tiempo de import del paquete el registro de modelos
aún no está poblado (``AppRegistryNotReady``); excepción #4 de
``no-lazy-imports.md``: ``importlib.import_module`` es una llamada de
función, no un ``import`` estático.
"""
import importlib

from django.apps import AppConfig


class HrRecruitmentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.hr_recruitment'
    label = 'hr_recruitment'
    verbose_name = 'Reclutamiento (hr.applicant)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``.
    #: módulo → nombre de la función ``apply_hr_recruitment_<archivo>_
    #: extensions`` que ``ready()`` invoca uniformemente. ``hr_employee.py``
    #: y ``res_partner.py`` NO aparecen aquí: no cuelgan código, sólo
    #: documentan un reverso automático (ver sus propios docstrings).
    _EXTENSIONES = {
        'addons.hr_recruitment.models.calendar': 'apply_hr_recruitment_calendar_extensions',
        'addons.hr_recruitment.models.digest': 'apply_hr_recruitment_digest_extensions',
        'addons.hr_recruitment.models.hr_department': 'apply_hr_recruitment_hr_department_extensions',
        'addons.hr_recruitment.models.hr_job': 'apply_hr_recruitment_hr_job_extensions',
        'addons.hr_recruitment.models.ir_attachment': 'apply_hr_recruitment_ir_attachment_extensions',
        'addons.hr_recruitment.models.ir_ui_menu': 'apply_hr_recruitment_ir_ui_menu_extensions',
        'addons.hr_recruitment.models.mail_activity_plan': 'apply_hr_recruitment_mail_activity_plan_extensions',
        'addons.hr_recruitment.models.res_company': 'apply_hr_recruitment_res_company_extensions',
        'addons.hr_recruitment.models.res_config_settings': 'apply_hr_recruitment_res_config_settings_extensions',
        'addons.hr_recruitment.models.res_users': 'apply_hr_recruitment_res_users_extensions',
        'addons.hr_recruitment.wizard.mail_activity_schedule': 'apply_hr_recruitment_mail_activity_schedule_extensions',
    }

    def ready(self):
        """Aplica lo que ``hr_recruitment`` cuelga de modelos ajenos.

        ``utm_campaign.py``/``utm_source.py`` NO están en ``_EXTENSIONES``:
        no declaran ``@api.ondelete`` (ausente en este ORM — ver sus
        docstrings), así que exponen un guard de módulo que quien orqueste
        el borrado invoca directo; no hay nada que colgar en ``ready()``.
        """
        for ruta, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(ruta), function_name)()
