"""AppConfig — ``addons.l10n_mx``.

La localización mexicana no declara modelos propios: **todo lo suyo cuelga de
modelos ajenos**. Por eso este AppConfig es casi todo ``ready()``: es el momento
equivalente al ``_inherit`` de la referencia, cuando el registro ya está poblado
y ``account.account`` existe para que se le pueda añadir su código del SAT.

El plan contable entra por otra vía: ``template_mx`` se importa aquí para que su
decorador ``@template('mx')`` registre las funciones en ``TEMPLATE_REGISTRY``.
Sin ese import el plan existiría en disco y no aparecería en la lista de planes
disponibles — el mismo modo de fallo silencioso que ``account`` evita
importando ``template_generic_coa``.
"""
import importlib

from django.apps import AppConfig


class L10nMxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.l10n_mx'
    label = 'l10n_mx'
    verbose_name = 'México — contabilidad'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``.
    #: El nombre de cada archivo espeja el de la referencia
    #: (``odoo19c: l10n_mx/models/*.py``).
    _EXTENSIONES = (
        'addons.l10n_mx.models.account_account',
        'addons.l10n_mx.models.account_move_line',
        'addons.l10n_mx.models.account_tax',
        'addons.l10n_mx.models.res_bank',
        'addons.l10n_mx.models.res_company',
        'addons.l10n_mx.models.res_config_settings',
    )

    def ready(self):
        """Cuelga la superficie mexicana y registra el plan de cuentas.

        ``importlib.import_module`` y no un ``import`` al top porque en tiempo
        de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de ``no-lazy-imports``,
        que sanciona exactamente esta forma: una llamada de función, no un
        statement ``import``. Mismo patrón que ``AccountConfig.ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_l10n_mx_extensions()
        importlib.import_module('addons.l10n_mx.models.template_mx')
