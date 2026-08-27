"""AppConfig — addons.account.

Fiel al addon ``account`` de Odoo (18/19): libro mayor de doble entrada. Núcleo
portado como paquete ``models/`` (un archivo por modelo). Datos de negocio
per-empresa (no plano de control): NO va en ``MULTIDB_CONTROL_PLANE_APPS``;
enruta a la BD de la ``company`` bajo N>1.

Depende de ``base`` (moneda), ``company`` (empresa) y ``users`` (party). Cross-app
``_inherit`` de Odoo (res.partner/res.company/res.currency) → FK/RELATED
(DEC-SALE-01).
"""
import importlib

from django.apps import AppConfig


class AccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account'
    label = 'account'
    verbose_name = 'Contabilidad (libro mayor de doble entrada)'

    #: Módulos que extienden modelos de OTROS addons — ≙ ``_inherit``.
    #: El nombre del archivo espeja el de la referencia
    #: (``odoo19c: account/models/{product,res_currency}.py``).
    #: El orden importa: ``res_company`` cuelga el impuesto por defecto que
    #: ``product`` lee para inicializar el suyo.
    #:
    #: Los 4 ``account_analytic_*``/``account_code_mapping`` extienden modelos
    #: del addon ``analytic`` (``account.analytic.{account,line,distribution
    #: .model,applicability}``) — cableados en tarea #520. Todos declaran
    #: ``apply_account_extensions()`` (mismo nombre en cada módulo — es lo que
    #: ``ready()`` invoca uniformemente abajo); antes de #520 se llamaban
    #: ``apply_account_analytic_*_extensions`` y NO estaban en esta tupla.
    #: ``account_code_mapping`` no aparece: no declara ningún modelo Django
    #: (divergencia de mecanismo, ver su docstring) y por tanto no tiene
    #: función que cablear.
    _EXTENSIONES = (
        'addons.account.models.res_company',
        'addons.account.models.product',
        'addons.account.models.res_currency',
        'addons.account.models.res_partner_bank',
        'addons.account.models.account_analytic_account',
        'addons.account.models.account_analytic_distribution_model',
        'addons.account.models.account_analytic_line',
        'addons.account.models.account_analytic_plan',
        # Tanda #75/#398 tramo 3 (2026-08-19) — los 18 módulos nuevos, todos
        # con `apply_account_extensions()` uniforme:
        'addons.account.models.account_document_import_mixin',
        'addons.account.models.account_journal_dashboard',
        'addons.account.models.account_move_line_tax_details',
        'addons.account.models.account_move_send',
        'addons.account.models.decimal_precision',
        'addons.account.models.digest',
        'addons.account.models.ir_actions_report',
        'addons.account.models.ir_attachment',
        'addons.account.models.mail_message',
        'addons.account.models.mail_template',
        'addons.account.models.mail_tracking_value',
        'addons.account.models.merge_partner_automatic',
        'addons.account.models.onboarding_onboarding',
        'addons.account.models.onboarding_onboarding_step',
        'addons.account.models.partner',
        'addons.account.models.product_catalog_mixin',
        'addons.account.models.res_country_group',
        'addons.account.models.res_users',
    )

    def ready(self):
        """Aplica lo que la contabilidad cuelga de modelos ajenos (T-B2a).

        Es el momento equivalente al ``_inherit`` de la referencia: aquí el
        registro de modelos ya está poblado, así que ``product.template``
        existe y se le puede añadir su cuenta de ingreso **sin que ``product``
        importe nada de contabilidad**.

        ``importlib.import_module`` y no un ``import`` al top porque en tiempo
        de import de este módulo el registro aún no está listo
        (``AppRegistryNotReady``). Es la excepción #4 de ``no-lazy-imports``,
        que sanciona exactamente esta forma: una llamada de función, no un
        statement ``import``. Mismo patrón que ``WebsiteSaleConfig.ready()``.
        """
        for ruta in self._EXTENSIONES:
            importlib.import_module(ruta).apply_account_extensions()
