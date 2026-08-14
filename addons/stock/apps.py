import importlib

from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.stock'
    verbose_name       = 'Inventario (stock)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. Cada
    #: uno expone ``apply_stock_<destino>_extensions()``; mismo criterio que
    #: ``AccountFleetConfig._EXTENSIONES``.
    _EXTENSIONES = (
        'addons.stock.models.product',
    )

    def ready(self):
        # Cuelga sobre `product.template` lo que `stock` le añade en la
        # referencia (`odoo19c: stock/models/product.py`). Ver ese módulo:
        # hoy porta `tracking`, el resto es alcance de la tarea #274.
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_stock_product_extensions()
        # Registra los receptores de notificación de este addon (T-035).
        # ``importlib.import_module`` —no un ``import`` statement— es la
        # excepción #4 sancionada para ``ready()``: el gate AST prohíbe
        # imports dentro de funciones y no tiene ``# noqa``.
        importlib.import_module(f'{self.name}.handlers')
