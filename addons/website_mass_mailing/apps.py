from django.apps import AppConfig


class WebsiteMassMailingConfig(AppConfig):
    """``website_mass_mailing`` — snippet/controlador de suscripción pública a
    la newsletter desde la tienda (Odoo ``website_mass_mailing``).

    Addon **sin modelos**: sólo expone la superficie HTTP pública
    (subscribe / confirm / unsubscribe) sobre los modelos de ``mass_mailing``.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.website_mass_mailing'
    label = 'website_mass_mailing'
