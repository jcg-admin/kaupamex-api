import importlib

from django.apps import AppConfig


class WebsiteSaleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.website_sale'
    verbose_name = 'Escaparate y carrito (website_sale)'

    def ready(self):
        """Aplica las extensiones de la tienda a modelos de otros addons.

        Es el momento equivalente al ``_inherit`` de la referencia: aquí el
        registro de modelos ya está poblado, así que ``product.template`` y
        ``sale.order`` existen y se les puede añadir lo suyo **sin que
        ``product`` ni ``sale`` importen nada del sitio**.

        ``importlib.import_module`` y no un ``import`` al top porque en tiempo
        de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de ``no-lazy-imports``,
        que sanciona exactamente esta forma: una llamada de función, no un
        statement ``import``.
        """
        module = importlib.import_module(
            'addons.website_sale.models.product_template')
        module.apply_website_extensions()

        # Recuperación de carrito abandonado (tarea #258): ``is_abandoned_cart``
        # y los métodos que lo consumen se cuelgan de ``sale.order``.
        sale_order_module = importlib.import_module(
            'addons.website_sale.models.sale_order')
        sale_order_module.apply_website_sale_order_extensions()

        # Contador de carritos abandonados del equipo de venta (tarea #568):
        # se cuelga de ``crm.team``, que es de ``sales_team``.
        #
        # Va **después** de ``sale_order``: su cómputo llama a
        # ``SaleOrder._search_abandoned_cart``, que es justo lo que la línea
        # anterior instala. El orden no es cosmético aunque hoy nadie lea el
        # campo durante el arranque.
        crm_team_module = importlib.import_module(
            'addons.website_sale.models.crm_team')
        crm_team_module.apply_website_sale_crm_team_extensions()

        # ``models/res_config_settings.py`` NO se invoca a propósito: es un
        # archivo de sólo docstring que declara su porte bloqueado (tarea
        # **#278**, quinto caso del árbol). Añadir una llamada no-op sería un
        # cableado muerto — mismo criterio que ``account_check_printing`` y
        # ``stock``, que tampoco lo cablean.
