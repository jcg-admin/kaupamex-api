"""Modelos del addon ``account`` — paquete espejo de ``odoo/addons/account/models/``.

Un archivo por modelo (monolito modular, como Odoo). Núcleo del libro mayor de
doble entrada:

- ``account_account.py``          → ``AccountAccount``          (plan de cuentas).
- ``account_account_tag.py``      → ``AccountAccountTag``       (casillas fiscales).
- ``account_group.py``            → ``AccountGroup``            (agrupación por rango de código).
- ``account_root.py``             → utilidades puras (prefijo de 2 dígitos; NO es modelo, ver docstring).
- ``account_fiscal_position.py``  → ``AccountFiscalPosition``   (posición fiscal).
- ``account_fiscal_position_account.py`` → ``AccountFiscalPositionAccount`` (mapeo de cuentas).
- ``account_journal.py``          → ``AccountJournal``          (diarios).
- ``account_journal_group.py``    → ``AccountJournalGroup``     (grupos de diarios).
- ``account_tax.py``              → ``AccountTax``              (impuestos).
- ``account_tax_group.py``        → ``AccountTaxGroup``         (grupo de impuestos).
- ``account_tax_repartition_line.py`` → ``AccountTaxRepartitionLine`` (reparto de un impuesto).
- ``account_move.py``             → ``AccountMove``             (asientos / facturas).
- ``account_move_line.py``        → ``AccountMoveLine``         (apuntes).
- ``account_payment.py``          → ``AccountPayment``          (pagos).
- ``account_payment_method.py``   → ``AccountPaymentMethod``, ``AccountPaymentMethodLine``
  (métodos de pago y su habilitación por diario).
- ``account_payment_term.py``     → ``AccountPaymentTerm``, ``AccountPaymentTermLine``
  (plazos de pago y sus cuotas).
- ``account_bank_statement.py``   → ``AccountBankStatement``    (estados de cuenta).
- ``account_bank_statement_line.py`` → ``AccountBankStatementLine`` (líneas bancarias).
- ``account_lock_exception.py``   → ``AccountLockException``    (excepciones de candado).
- ``account_cash_rounding.py``    → ``AccountCashRounding``     (redondeo de efectivo).
- ``account_incoterms.py``        → ``AccountIncoterms``        (Incoterms).
- ``account_partial_reconcile.py`` → ``AccountPartialReconcile`` (emparejamiento debe/haber).
- ``account_full_reconcile.py``    → ``AccountFullReconcile``    (número de conciliación total).
- ``account_reconcile_model.py``   → ``AccountReconcileModel`` + ``AccountReconcileModelLine``
  (reglas de conciliación automática).
- ``account_report.py``            → ``AccountReport`` + ``AccountReportLine``
  + ``AccountReportExpression`` + ``AccountReportColumn``
  + ``AccountReportExternalValue`` (el árbol declarativo de un reporte
  contable; el motor de evaluación de fórmulas NO se porta aquí — ver el
  docstring del archivo).

Extensiones de modelos ajenos — ≙ ``_inherit``, NO se exportan aquí
===================================================================

Dos módulos más espejan la referencia y **no** declaran modelos: cuelgan
campos y métodos de modelos que ``account`` no posee. No se importan desde
este ``__init__`` a propósito — su import es tardío, desde
``AccountConfig.ready()``, porque en tiempo de import el registro de modelos
aún no está poblado.

- ``product.py``      → cuelga de ``product.template``/``category``/``product``
  (impuestos de venta y compra, cuentas de ingreso y gasto, etiquetas).
- ``res_currency.py`` → cuelga de ``res.currency`` el guard que impide
  reducir la precisión de una divisa ya usada en apuntes.

Cuatro módulos más de la familia ``account.analytic.*`` (tarea #398, tramo 2)
declaran su ``apply_account_extensions()`` con el mismo patrón — cableados en
``AccountConfig._EXTENSIONES`` por la tarea #520 (esta prosa decía "todavía
no cableados"; era estado stale, corregido 2026-08-19). La tanda #75/#398
tramo 3 añadió 18 módulos más con el patrón uniforme — el índice completo es
la propia tupla ``_EXTENSIONES`` de ``apps.py``, que es su único dueño:

- ``account_analytic_account.py``      → no-op documentado (BLOQUEADO, ver
  su docstring); cuelga de ``analytic.account.analytic.account``.
- ``account_analytic_distribution_model.py`` → cuelga ``prefix_placeholder``
  (``store=False``) de ``analytic.account.analytic.distribution.model``.
- ``account_analytic_line.py``         → no-op documentado (BLOQUEADO, ver
  su docstring); cuelga de ``analytic.account.analytic.line``.
- ``account_analytic_plan.py``         → amplía ``business_domain`` y cuelga
  ``display_account_prefix``/``account_prefix_placeholder`` (``store=False``)
  de ``analytic.account.analytic.applicability``.

``account_code_mapping.py`` no declara ``apply_*_extensions()``: no crea
modelo (divergencia de mecanismo declarada en su propio docstring).
"""
from .account_account import AccountAccount
from .account_account_tag import AccountAccountTag
from .account_bank_statement import AccountBankStatement
from .account_bank_statement_line import AccountBankStatementLine
from .account_cash_rounding import AccountCashRounding
from .account_fiscal_position import AccountFiscalPosition
from .account_fiscal_position_account import AccountFiscalPositionAccount
from .account_full_reconcile import AccountFullReconcile
from .account_group import AccountGroup
from .account_incoterms import AccountIncoterms
from .account_journal import AccountJournal
from .account_journal_group import AccountJournalGroup
from .account_lock_exception import AccountLockException
from .account_move import AccountMove
from .account_move_line import AccountMoveLine
from .account_partial_reconcile import AccountPartialReconcile
from .account_payment import AccountPayment
from .account_payment_method import AccountPaymentMethod, AccountPaymentMethodLine
from .account_payment_term import AccountPaymentTerm, AccountPaymentTermLine
from .account_reconcile_model import AccountReconcileModel, AccountReconcileModelLine
from .account_report import (
    AccountReport,
    AccountReportColumn,
    AccountReportExpression,
    AccountReportExternalValue,
    AccountReportLine,
)
from .account_root import (
    account_root_from_code,
    account_root_name,
    account_root_parent,
)
from .account_tax import AccountTax
from .account_tax_group import AccountTaxGroup
from .account_tax_repartition_line import AccountTaxRepartitionLine
from .chart_template import ChartTemplate, template
# Importar una plantilla REGISTRA sus funciones (ver la nota de divergencia del
# registro en chart_template.py). Sin estos imports el plan 'generic_coa' no
# existiría para el cargador, y ninguna empresa recibiría sus diarios.
from . import template_generic_coa  # noqa: F401

__all__ = [
    'AccountAccount',
    'AccountAccountTag',
    'AccountBankStatement',
    'AccountBankStatementLine',
    'AccountCashRounding',
    'AccountFiscalPosition',
    'AccountFiscalPositionAccount',
    'AccountFullReconcile',
    'AccountGroup',
    'AccountIncoterms',
    'AccountJournal',
    'AccountJournalGroup',
    'AccountLockException',
    'AccountMove',
    'AccountMoveLine',
    'AccountPartialReconcile',
    'AccountPayment',
    'AccountPaymentMethod',
    'AccountPaymentMethodLine',
    'AccountPaymentTerm',
    'AccountPaymentTermLine',
    'AccountReconcileModel',
    'AccountReconcileModelLine',
    'AccountReport',
    'AccountReportColumn',
    'AccountReportExpression',
    'AccountReportExternalValue',
    'AccountReportLine',
    'AccountTax',
    'AccountTaxGroup',
    'AccountTaxRepartitionLine',
    'ChartTemplate',
    'template',
    'account_root_from_code',
    'account_root_name',
    'account_root_parent',
]
