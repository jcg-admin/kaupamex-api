import importlib

from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.hr'
    verbose_name       = 'Empleados (hr.department, hr.job)'

    #: Extensiones que hr cuelga de modelos ajenos — ≙ ``_inherit`` de la
    #: referencia. Mismo patrón que ``StockConfig._EXTENSIONES``: módulo →
    #: función, importado tarde desde ``ready()`` porque en tiempo de import
    #: el registro de modelos aún no está poblado (excepción #4 de
    #: ``no-lazy-imports``: llamada de función, no statement ``import``).
    _EXTENSIONES = {
        'addons.hr.models.discuss_channel': 'apply_hr_discuss_channel_extensions',
        'addons.hr.models.ir_ui_menu': 'apply_hr_ir_ui_menu_extensions',
        'addons.hr.models.mail_activity_plan': 'apply_hr_mail_activity_plan_extensions',
        'addons.hr.models.mail_activity_plan_template': 'apply_hr_mail_activity_plan_template_extensions',
        'addons.hr.models.mail_alias': 'apply_hr_mail_alias_extensions',
        'addons.hr.models.res_company': 'apply_hr_res_company_extensions',
        'addons.hr.models.res_config_settings': 'apply_hr_res_config_settings_extensions',
        'addons.hr.models.res_partner': 'apply_hr_res_partner_extensions',
        'addons.hr.models.res_partner_bank': 'apply_hr_res_partner_bank_extensions',
        'addons.hr.models.res_users': 'apply_hr_res_users_extensions',
        'addons.hr.models.resource': 'apply_hr_resource_extensions',
        'addons.hr.models.resource_calendar': 'apply_hr_resource_calendar_extensions',
        'addons.hr.models.resource_calendar_leaves': 'apply_hr_resource_calendar_leaves_extensions',
        'addons.hr.wizard.mail_activity_schedule': 'apply_hr_mail_activity_schedule_extensions',
    }

    def ready(self):
        """Aplica lo que hr cuelga de modelos ajenos (resource, res_*, mail)."""
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
