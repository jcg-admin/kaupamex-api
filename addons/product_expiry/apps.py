"""AppConfig — ``addons.product_expiry``.

La extensión se aplica en ``ready()``, cuando el registro de modelos ya está
poblado y ``add_to_class``/``chain_method`` sobre una clase ajena no rompe con
``AppRegistryNotReady``. Mismo criterio que ``account_fleet``.
"""
import importlib

from django.apps import AppConfig


class ProductExpiryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.product_expiry'
    label              = 'product_expiry'
    verbose_name       = 'Caducidad de productos (product_expiry)'

    #: Los ocho módulos que espejan ``odoo19c: product_expiry/models/*.py``,
    #: en el orden en que la referencia los importa. Cuatro cuelgan símbolos y
    #: cuatro son no-op declarados (su modelo destino no está portado; cada
    #: docstring nombra la causa y su tarea sucesora).
    _EXTENSIONES = (
        'addons.product_expiry.models.product_product',
        'addons.product_expiry.models.production_lot',
        'addons.product_expiry.models.res_config_settings',
        'addons.product_expiry.models.stock_move',
        'addons.product_expiry.models.stock_move_line',
        'addons.product_expiry.models.stock_picking',
        'addons.product_expiry.models.stock_quant',
        'addons.product_expiry.models.stock_rule',
    )

    def ready(self):
        """Cuelga el vocabulario de caducidad sobre ``product``/``stock``.

        ``importlib.import_module`` y no un ``import`` al top: es la excepción
        #4 de ``no-lazy-imports.md`` (una llamada de función, no un statement
        ``import``), sancionada exactamente para ``ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_product_expiry_extensions()
