from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.hr'
    verbose_name       = 'Empleados (hr.department, hr.job)'
