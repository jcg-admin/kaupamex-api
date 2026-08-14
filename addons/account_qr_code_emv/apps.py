"""AppConfig — ``addons.account_qr_code_emv``.

Igual que ``l10n_mx`` (mismo criterio: puente que sólo cuelga de modelos
ajenos, sin modelos propios): la extensión de ``res.partner.bank`` se aplica
en ``ready()``, cuando el registro de modelos ya está poblado y
``add_to_class``/``setattr`` sobre una clase ya definida no rompe con
``AppRegistryNotReady``.

Pendiente de wiring (fuera del alcance de este addon — ver
``models/res_bank.py``, sección "Divergencias declaradas", punto 4): este
``AppConfig`` sólo se ejecuta si ``'addons.account_qr_code_emv'`` está en
``INSTALLED_APPS`` (``config/settings/base.py``, no tocado por este agente).
"""
import importlib

from django.apps import AppConfig


class AccountQrCodeEmvConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_qr_code_emv'
    label = 'account_qr_code_emv'
    verbose_name = 'Puente QR EMV Merchant-Presented (res.partner.bank)'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``. Mismo
    #: patrón que ``L10nMxConfig._EXTENSIONES``: un elemento hoy, tupla por
    #: si una localización futura necesita colgar un segundo archivo aquí.
    _EXTENSIONES = (
        'addons.account_qr_code_emv.models.res_bank',
    )

    def ready(self):
        """Cuelga el vocabulario EMV sobre ``base.ResPartnerBank``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un
        statement ``import``, así que el gate AST la deja pasar. Mismo
        patrón que ``L10nMxConfig.ready()``/``AccountConfig.ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_account_qr_code_emv_extensions()
