"""AppConfig — ``addons.account_peppol``.

Cinco módulos espejan archivos de ``odoo19c: account_peppol/models/`` y cuelgan
sus símbolos vivos sobre modelos ajenos (``account_edi_proxy_client.user``,
``res.company``, ``res.partner``, ``account.move``, ``account.journal``). Las
extensiones se aplican en ``ready()``, cuando el registro de modelos ya está
poblado y ``chain_method`` sobre una clase ajena no rompe con
``AppRegistryNotReady`` — mismo criterio que ``project_account`` /
``account_debit_note``.

**Orden dentro del dict, y por qué importa.** ``account_edi_proxy_user`` va
primero: ``res_company`` y ``res_partner`` consultan
``AccountEdiProxyUser._get_peppol_proxy_types()`` y ``_get_can_send_domain()``,
que ese módulo instala. Python conserva el orden de inserción del dict desde
3.7, así que el bucle respeta esta secuencia.

Los otros cinco archivos de ``models/`` **no** entran aquí: están bloqueados
enteros y son documentación (ver ``models/__init__.py``).
"""
import importlib

from django.apps import AppConfig


class AccountPeppolConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'addons.account_peppol'
    label              = 'account_peppol'
    verbose_name       = 'Peppol (account_peppol)'

    #: Módulo → función. Mismo patrón que ``AccountDebitNoteConfig``.
    _EXTENSIONES = {
        'addons.account_peppol.models.account_edi_proxy_user':
            'apply_account_peppol_account_edi_proxy_user_extensions',
        'addons.account_peppol.models.res_company':
            'apply_account_peppol_res_company_extensions',
        'addons.account_peppol.models.res_partner':
            'apply_account_peppol_res_partner_extensions',
        'addons.account_peppol.models.account_move':
            'apply_account_peppol_account_move_extensions',
        'addons.account_peppol.models.account_journal':
            'apply_account_peppol_account_journal_extensions',
    }

    def ready(self):
        """Cuelga el vocabulario Peppol sobre los cinco modelos ajenos.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4
        de ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar.
        """
        for module_path, function_name in self._EXTENSIONES.items():
            getattr(importlib.import_module(module_path), function_name)()
