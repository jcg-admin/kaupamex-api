import importlib

from django.apps import AppConfig


class WebsiteSaleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.website_sale'
    verbose_name = 'Escaparate y carrito (website_sale)'

    def ready(self):
        """Aplica las extensiones de la tienda a modelos de otros addons.

        Es el momento equivalente al ``_inherit`` de la referencia: aquí el
        registro de modelos ya está poblado, así que ``product.template``
        existe y se le puede añadir la publicación **sin que ``product``
        importe nada del sitio**.

        ``importlib.import_module`` y no un ``import`` al top porque en tiempo
        de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de ``no-lazy-imports``,
        que sanciona exactamente esta forma: una llamada de función, no un
        statement ``import``.
        """
        module = importlib.import_module(
            'addons.website_sale.models.product_template')
        module.apply_website_extensions()
