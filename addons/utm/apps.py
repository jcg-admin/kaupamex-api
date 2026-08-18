from django.apps import AppConfig


class UtmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.utm'
    verbose_name       = 'Rastreadores UTM (campaña, medio, fuente)'
