from django.apps import AppConfig


class BusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.bus'
    verbose_name = 'Bus de notificaciones — cola persistida (DEC-AF-06)'
