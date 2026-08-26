"""AppConfig — ``addons.account_check_printing``.

Tres extensiones sobre modelos AJENOS (≙ ``_inherit``) más una señal — todas
se aplican en ``ready()``, cuando el registro de apps ya está poblado y
``chain_method``/``add_to_class``/``connect`` sobre una clase ya definida no
rompe con ``AppRegistryNotReady``. Mismo criterio que
``AccountConfig``/``L10nMxConfig``/``AccountQrCodeEmvConfig``/
``AccountDebitNoteConfig``.

Las tres extensiones cuelgan un MÉTODO sobre un modelo de otro addon —
``chain_method`` (H-API-364), nunca la guarda ``hasattr``: si mañana otro
addon también extiende ``ResCurrency.amount_to_text`` o
``AccountPaymentMethod._get_payment_method_information``, la cadena preserva
ambos en vez de que gane el que instale ``INSTALLED_APPS`` primero.
"""
import importlib

from django.apps import AppConfig
from django.db.models.signals import post_save


class AccountCheckPrintingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_check_printing'
    label = 'account_check_printing'
    verbose_name = 'Contabilidad — Impresión de cheques'

    #: Módulos que extienden modelos de OTRO addon vía ``chain_method`` — un
    #: elemento por modelo ajeno tocado. Mismo patrón que
    #: ``AccountQrCodeSepaConfig._EXTENSIONES``.
    #: RETIRADA 2026-08-26 la extensión de ``ir.sequence``: ``get_next_char``
    #: es API de ``base`` desde el porte completo de ``ir_sequence.py``, y la
    #: referencia NO declara ``ir_sequence.py`` en este addon —lo consume, no
    #: lo extiende (siete addons de ``odoo19c`` lo llaman). Ver H-API-792.
    _EXTENSIONES = (
        ('addons.account_check_printing.models.res_currency',
         'apply_account_check_printing_currency_extensions'),
        ('addons.account_check_printing.models.account_payment_method',
         'apply_account_check_printing_payment_method_extensions'),
    )

    def ready(self):
        """Cuelga las dos extensiones y conecta la señal de auto-provisión.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un
        statement ``import``, así que el gate AST la deja pasar. Mismo
        patrón que ``AccountConfig.ready()``/``AccountDebitNoteConfig.ready()``.
        """
        for ruta, funcion in self._EXTENSIONES:
            getattr(importlib.import_module(ruta), funcion)()

        # Divergencia 2 de ``models/account_journal.py``: esta capa ORM no
        # tiene un ``create()`` de instancia que encadenar (Django expone
        # ``Model.objects.create()``, no un método de clase Odoo-style), así
        # que la auto-provisión de la secuencia de cheques en diarios de
        # banco NUEVOS se hace por señal — mismo patrón que
        # ``account/models/res_company.py::apply_account_extensions`` usa
        # para ``load_chart_for_new_company``.
        account_journal = importlib.import_module(
            'addons.account_check_printing.models.account_journal')
        post_save.connect(
            account_journal.on_journal_saved,
            sender=account_journal.AccountJournal,
            dispatch_uid='account_check_printing.sync_bank_journal_check_sequence',
        )
