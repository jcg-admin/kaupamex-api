import importlib

from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.stock'
    verbose_name       = 'Inventario (stock)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. La
    #: clave es el módulo; el valor, la función que aplica su extensión.
    #:
    #: Era una tupla con el nombre de la función **hardcodeado** en el bucle
    #: (``apply_stock_product_extensions``), así que sólo admitía un destino:
    #: el segundo módulo habría llamado a la función del primero. Pasa a mapa
    #: al entrar ``res_partner`` y ``res_company`` (tarea #257).
    _EXTENSIONES = {
        'addons.stock.models.product': 'apply_stock_product_extensions',
        'addons.stock.models.res_partner': 'apply_stock_res_partner_extensions',
        'addons.stock.models.res_company': 'apply_stock_res_company_extensions',
    }

    def ready(self):
        # Cuelga sobre `product.template`, `res.partner` y `res.company` lo que
        # `stock` les añade en la referencia (`odoo19c: stock/models/*.py`).
        for ruta, funcion in self._EXTENSIONES.items():
            getattr(importlib.import_module(ruta), funcion)()
        # Registra los receptores de notificación de este addon (T-035).
        # ``importlib.import_module`` —no un ``import`` statement— es la
        # excepción #4 sancionada para ``ready()``: el gate AST prohíbe
        # imports dentro de funciones y no tiene ``# noqa``.
        importlib.import_module(f'{self.name}.handlers')
