"""
Models — addons.settings_app

Addon disuelto (adaptar-familias-odoo-monolito-modular): ya no define
modelos. Permanece como controlador de los endpoints UC-CFG. Destinos:

- ``SiteSettings``   → ``addons.base.models.res_config_settings``
  (~ ``res.config.settings``, H-SETTINGS-02).
- ``PaymentGateway`` → ``addons.payment.models.payment_provider``
  (~ ``payment.provider``, H-PAYMENTS-05).
- ``ShippingMethod`` → ``addons.delivery.models``
  (~ ``delivery.carrier``, H-SETTINGS-03).
- ``StaticPage``/``StaticPageVersion``/``Banner`` → ``addons.website``
  (H-SETTINGS-01).
"""
