"""AppConfig — ``addons.account_payment``.

Igual que ``account_add_gln``/``account_debit_note``/``account_fleet``
(mismo criterio: puente sin tocar la migración de los modelos ajenos que
extiende): las propiedades no-almacenadas y los métodos colgados se aplican
en ``ready()``, cuando el registro de modelos ya está poblado y
``chain_method``/``setattr`` sobre una clase ya definida no rompe con
``AppRegistryNotReady``.

Wiring pendiente (fuera del alcance de este agente — no se toca
``config/settings/base.py``): este ``AppConfig`` sólo se ejecuta si
``'addons.account_payment'`` está en ``INSTALLED_APPS``, después de
``'addons.account'`` y ``'addons.payment'`` (dependencias de sus 4 modelos
RELATED — ver ``migrations/0001_initial.py``).
"""
import importlib

from django.apps import AppConfig


class AccountPaymentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_payment'
    label = 'account_payment'
    verbose_name = 'Contabilidad — Pagos en línea (account_payment)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``. El
    #: nombre de cada archivo espeja el de la referencia (``odoo19c:
    #: account_payment/models/*.py``). Cada uno define
    #: ``apply_account_payment_extensions()`` — mismo nombre en los 6,
    #: mismo criterio que ``AccountFleetConfig._EXTENSIONES``.
    #:
    #: ``account_bank_statement_line`` NO aparece: 0 símbolos portados (ver
    #: su docstring), así que no declara función de extensión — llamarla
    #: sería ceremonia sobre un módulo vacío.
    _EXTENSIONES = (
        'addons.account_payment.models.account_payment',
        'addons.account_payment.models.account_payment_method',
        'addons.account_payment.models.account_payment_method_line',
        'addons.account_payment.models.account_journal',
        'addons.account_payment.models.account_move',
        'addons.account_payment.models.payment_provider',
    )

    def ready(self):
        """Cuelga el vocabulario cruzado sobre ``account``/``payment``.

        ``importlib.import_module`` y no un ``import`` al top porque en
        tiempo de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de
        ``no-lazy-imports.md``: una llamada de función, no un statement
        ``import``. Mismo patrón que ``AccountFleetConfig.ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_account_payment_extensions()
