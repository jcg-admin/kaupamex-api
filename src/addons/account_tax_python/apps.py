"""AppConfig — ``addons.account_tax_python``.

Fiel al addon ``account_tax_python`` de Odoo 19 (``odoo-tools@622ddc2a``,
``odoo19c: addons/account_tax_python/__manifest__.py``): agrega un
``amount_type`` de fórmula Python al impuesto. La referencia declara
``depends: ['account']``; aquí no hay auto-install (registro explícito en
``INSTALLED_APPS``, ver la nota de alcance abajo).

Cross-app ``_inherit`` de Odoo sobre ``account.tax`` → dos mecanismos
distintos en este ``ready()``, según si lo que se cuelga es DATO o
COMPORTAMIENTO ya existente (ver ``models/account_tax.py`` y
``models/account_tax_extensions.py`` para el detalle símbolo por símbolo):

- **Dato nuevo** (``formula``) → modelo satélite ``AccountTaxFormula``
  (``OneToOne`` a ``account.AccountTax``), declarado normal en
  ``models/__init__.py`` — no necesita ``ready()``.
- **Comportamiento que YA existe y hay que extender**
  (``_eval_tax_amount_fixed_amount``) + **comportamiento que NO existe y
  hay que agregar** (``_eval_taxes_computation_prepare_product_fields``/
  ``_uom_fields``) → el patrón ``setattr``/captura-y-extiende que este
  árbol ya usa (``account/models/res_company.py``, ``l10n_mx``,
  ``account_debit_note``) — ver
  ``models/account_tax_extensions.py::apply_account_tax_python_extensions``.

**Fuera de este alcance** (el porte se restringió a
``src/addons/account_tax_python/`` — "no tocar ningún otro addon"):

1. Registrar ``addons.account_tax_python`` en ``INSTALLED_APPS``
   (``config/settings/base.py``, después de ``addons.account``). Sin ese
   registro Django no descubre esta app ni corre su migración inicial.
2. Agregar ``('code', 'Fórmula personalizada')`` a
   ``account.AccountTax.AMOUNT_TYPES`` (``account/models/account_tax.py``)
   — GAP documentado en ``models/account_tax.py`` con su sucesor exacto.
3. Los dos parámetros ``product=``/``product_uom=`` que le faltan a
   ``account: AccountTaxQuerySet._get_tax_details``/``compute_all`` — GAP
   documentado en el mismo docstring, con su sucesor exacto.
"""
import importlib

from django.apps import AppConfig


class AccountTaxPythonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_tax_python'
    label = 'account_tax_python'
    verbose_name = 'Contabilidad — Impuestos con fórmula Python'

    def ready(self):
        """Cuelga los ganchos de ``account.AccountTax``/``AccountTaxQuerySet``.

        ``importlib.import_module`` y no un ``import`` al top porque en
        tiempo de import de este módulo el registro de apps aún no está
        poblado (``AppRegistryNotReady``) — excepción #4 de
        ``no-lazy-imports``: una llamada de función, no un statement
        ``import``. Mismo patrón que ``AccountConfig.ready()`` /
        ``L10nMxConfig.ready()`` / ``AccountDebitNoteConfig.ready()``.
        """
        importlib.import_module(
            'addons.account_tax_python.models.account_tax_extensions'
        ).apply_account_tax_python_extensions()
