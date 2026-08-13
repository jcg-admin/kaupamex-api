"""AppConfig — ``addons.base_iban``.

Mismo criterio que ``account_qr_code_sepa`` y ``l10n_mx``: un puente que sólo
cuelga métodos de un modelo ajeno, sin modelos propios, aplica su extensión en
``ready()`` — cuando el registro de modelos ya está poblado y ``setattr`` sobre
una clase ya definida no rompe con ``AppRegistryNotReady``.
"""
import importlib

from django.apps import AppConfig


class BaseIbanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.base_iban'
    label = 'base_iban'
    verbose_name = 'Base — Cuentas bancarias IBAN'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``.
    _EXTENSIONS = (
        'addons.base_iban.models.res_partner_bank',
    )

    def ready(self):
        """Cuelga la superficie IBAN sobre ``base.ResPartnerBank``.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4 de
        ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for path in self._EXTENSIONS:
            importlib.import_module(path).apply_base_iban_extensions()
