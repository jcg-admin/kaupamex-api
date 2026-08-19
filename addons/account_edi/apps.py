"""AppConfig — ``addons.account_edi``.

Fiel al addon ``account_edi`` de Odoo (18/19): el registro genérico de
formatos de facturación electrónica y el ciclo de vida de sus documentos
(``account.edi.format``/``account.edi.document``), más lo que cuelga sobre
``account`` (``account.move``, ``account.journal``, ``account.move.send``,
``account.resequence.wizard``) y sobre ``base`` (``ir.attachment``,
``ir.actions.report`` — este último bloqueado, ver su docstring).

Depende de ``account`` (todo lo que extiende) y, transitivamente, de
``base``. Ningún addon ``l10n_*_edi`` está portado todavía — ``account.edi.
format`` existe vacío hasta que uno lo sea (ver ``models/
account_edi_format.py``).
"""
import importlib

from django.apps import AppConfig


class AccountEdiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_edi'
    label = 'account_edi'
    verbose_name = 'Facturación electrónica — EDI (base)'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``. Todos
    #: declaran ``apply_account_edi_extensions()`` (mismo nombre en cada
    #: módulo — lo que ``ready()`` invoca uniformemente abajo), incluidos
    #: los que declaran modelos NUEVOS propios (no-op documentado, mismo
    #: criterio que ``AccountConfig._EXTENSIONES``).
    _EXTENSIONS = (
        'addons.account_edi.models.account_edi_format',
        'addons.account_edi.models.account_edi_document',
        'addons.account_edi.models.account_journal',
        'addons.account_edi.models.account_move',
        'addons.account_edi.models.account_move_send',
        'addons.account_edi.models.ir_attachment',
        'addons.account_edi.models.ir_actions_report',
        'addons.account_edi.wizard.account_resequence',
    )

    def ready(self):
        """Aplica lo que ``account_edi`` cuelga de modelos ajenos.

        ``importlib.import_module`` y no un ``import`` al top — excepción
        #4 de ``no-lazy-imports.md``: es una llamada de función, no un
        statement ``import``, así que el gate AST la deja pasar. Mismo
        patrón que ``AccountConfig.ready()``.
        """
        for ruta in self._EXTENSIONS:
            importlib.import_module(ruta).apply_account_edi_extensions()
