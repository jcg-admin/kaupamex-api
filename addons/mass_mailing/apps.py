"""AppConfig del addon ``mass_mailing`` (hogar Odoo de la newsletter)."""
from django.apps import AppConfig


class MassMailingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.mass_mailing'
    label = 'mass_mailing'
    verbose_name = 'Mass Mailing'
