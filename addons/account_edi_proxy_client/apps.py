"""AppConfig — ``addons.account_edi_proxy_client``.

Fiel al addon ``account_edi_proxy_client`` de Odoo (18/19): el cliente
genérico del proxy de Odoo S.A. que registra y autentica usuarios de un
formato EDI concreto (PEPPOL, factura-e, …). Ningún ``l10n_*_edi`` está
portado todavía — ``proxy_type`` (Selection) queda sin opciones hasta que
uno lo sea, mismo criterio que ``account.edi.format`` en ``account_edi``.

Depende de ``account`` (transitivamente, vía ``account_edi``) y
``certificate`` (``CertificateKey`` para cifrado/firma).
"""
import importlib

from django.apps import AppConfig


class AccountEdiProxyClientConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_edi_proxy_client'
    label = 'account_edi_proxy_client'
    verbose_name = 'Cliente del proxy EDI (Odoo Access Point)'

    #: Todos declaran ``apply_account_edi_proxy_client_extensions()`` —
    #: incluidos los que declaran el modelo nuevo (no-op documentado, mismo
    #: criterio que ``AccountEdiConfig._EXTENSIONS``).
    _EXTENSIONS = (
        'addons.account_edi_proxy_client.models.account_edi_proxy_user',
        'addons.account_edi_proxy_client.models.key',
        'addons.account_edi_proxy_client.models.res_company',
    )

    def ready(self):
        """Aplica lo que este addon cuelga de modelos ajenos.

        ``importlib.import_module`` y no un ``import`` al top — excepción
        #4 de ``no-lazy-imports.md``. Mismo patrón que
        ``AccountEdiConfig.ready()``.
        """
        for ruta in self._EXTENSIONS:
            importlib.import_module(ruta).apply_account_edi_proxy_client_extensions()
