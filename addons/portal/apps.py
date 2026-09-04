"""AppConfig — addons.portal (Odoo portal)."""
import importlib

from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.portal'
    verbose_name = 'Portal — separación backoffice / cliente'

    def ready(self):
        # Las dos guardas de edición del partner (``_can_edit_country`` y
        # ``can_edit_vat``) son el ESLABÓN BASE de una cadena que ``sale``
        # continúa: su fuente escribe ``super()._can_edit_country()``. Por eso
        # se cuelgan como métodos aquí y no quedan como funciones de módulo —
        # ver el docstring de ``models/res_partner.py``.
        #
        # ``portal`` va en la posición 67 de ``LOCAL_APPS`` y ``sale`` en la
        # 93 (orden topológico derivado del grafo de ``depends``), así que
        # este eslabón está instalado cuando ``sale`` lo envuelve.
        #
        # ``importlib.import_module`` es la excepción #4 sancionada para
        # ``ready()``: es una llamada de función, no un statement ``import``.
        importlib.import_module(f'{self.name}.models.res_partner') \
            .apply_portal_partner_extensions()
