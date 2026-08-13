"""AppConfig — ``addons.account_fleet``.

Igual que ``account`` (sobre ``product``/``res.company``/``res.currency``),
``l10n_mx`` y ``account_qr_code_emv``/``account_qr_code_sepa`` (mismo
criterio: puente sin modelos propios, todo cuelga de modelos ajenos): la
extensión se aplica en ``ready()``, cuando el registro de modelos ya está
poblado y ``add_to_class``/``setattr`` sobre una clase ya definida no rompe
con ``AppRegistryNotReady``.

Wiring pendiente (fuera del alcance de este agente — ver ``__init__.py`` del
paquete, sección "Wiring pendiente"): este ``AppConfig`` sólo se ejecuta si
``'addons.account_fleet'`` está en ``INSTALLED_APPS``
(``config/settings/base.py``, no tocado por este agente).
"""
import importlib

from django.apps import AppConfig


class AccountFleetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_fleet'
    label = 'account_fleet'
    verbose_name = 'Puente Contabilidad ↔ Flota (account_fleet)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia (``odoo19c:
    #: account_fleet/models/*.py``). Cada uno define ``apply_account_fleet_
    #: extensions()`` — mismo nombre de función en los tres, mismo criterio
    #: que ``AccountConfig._EXTENSIONES`` (``apply_account_extensions`` en
    #: ``product.py``/``res_company.py``/``res_currency.py``).
    _EXTENSIONES = (
        'addons.account_fleet.models.account_move',
        'addons.account_fleet.models.fleet_vehicle',
        'addons.account_fleet.models.fleet_vehicle_log_services',
    )

    def ready(self):
        """Cuelga el vocabulario cruzado sobre ``account``/``fleet``.

        ``importlib.import_module`` y no un ``import`` al top porque en
        tiempo de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de
        ``no-lazy-imports.md``, que sanciona exactamente esta forma: una
        llamada de función, no un statement ``import``. Mismo patrón que
        ``AccountConfig.ready()``/``L10nMxConfig.ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_account_fleet_extensions()
