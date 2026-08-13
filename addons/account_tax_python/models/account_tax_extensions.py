"""Ganchos de ``account.AccountTax``/``AccountTaxQuerySet`` — la mitad de
``account_tax.py`` de la referencia que necesita colgarse de un modelo
ajeno (``_inherit`` en la fuente).

Por qué este archivo está separado de ``account_tax.py``
=============================================================

``AccountTaxFormula`` (modelo propio, dato nuevo) y estos ganchos
(comportamiento que se cuelga de clases YA definidas en ``account``) tienen
necesidades de import opuestas — mismo criterio que
``account_debit_note/models/account_move_sequence.py`` ya fijó para el
mismo problema:

- El modelo necesita import normal (``models/__init__.py``): Django sólo
  detecta modelos para migraciones si su módulo se importa en la fase de
  carga de apps.
- Estos ganchos necesitan **capturar** ``AccountTax._eval_tax_amount_fixed_
  amount`` — la función concreta ya definida en ``account`` — para poder
  llamarla desde la versión extendida. El patrón que este árbol ya usa para
  "colgar algo de un modelo ajeno" es siempre diferir a
  ``AppConfig.ready()``: es el único punto donde el registro de apps está
  garantizado completo sin depender del orden de ``INSTALLED_APPS``.

Dos formas de gancho, según si el símbolo ya existe
=======================================================

- ``_eval_tax_amount_fixed_amount`` **ya existe** en ``account.AccountTax``
  (lógica real para ``amount_type == 'fixed'``). Se captura como variable de
  módulo — ejecutado UNA sola vez, la primera vez que Python importa este
  módulo (``sys.modules`` lo cachea, así que una segunda llamada a
  ``apply_account_tax_python_extensions()`` no re-captura ni re-envuelve) —
  y la versión nueva la invoca explícitamente: el equivalente funcional de
  ``super()`` cuando no hay MRO de por medio.
- ``_eval_taxes_computation_prepare_product_fields``/``_uom_fields``
  **no existen** en ``AccountTaxQuerySet`` (verificado: ``grep -c
  "_eval_taxes_computation_prepare" account/models/account_tax.py`` → 0).
  Se agregan con el patrón "el primero que llega gana"
  (``setattr(Modelo, nombre, funcion) if not hasattr(...)``), el mismo que
  ``account: models/res_company.py``/``l10n_mx``/``account_qr_code_sepa``
  ya usan para métodos que la referencia declara con ``super()`` contra una
  base Odoo que aquí no existe (retorna ``set()`` — el equivalente es
  arrancar en ``set()`` sin ``super()`` que llamar).

Qué extienden (fiel a la referencia, símbolo por símbolo)
==============================================================

``_eval_tax_amount_fixed_amount`` — ≙ ``odoo19c: account_tax_python/
models/account_tax.py:116-120``: si ``amount_type == 'code'``, despacha a
la fórmula del ``AccountTaxFormula`` vinculado; si no, delega en el
comportamiento base (el ``super()`` de la referencia).

``_eval_taxes_computation_prepare_product_fields``/``_uom_fields`` — ≙
``:36-48``: agregan los campos de producto/uom que las fórmulas de los
impuestos ``'code'`` del queryset necesitan. Ver el GAP documentado en
``account_tax.py`` (módulo hermano): estos hooks existen y son correctos,
pero ``account: AccountTaxQuerySet._get_tax_details`` no los invoca todavía
— cerrarlo es tarea de ``account``, fuera de este alcance.

Divergencia Decimal↔float — dónde vive
=========================================

``account`` opera en ``Decimal``; la fórmula de ``account_tax_python``
opera en tipos JSON-primitivos (``float``/``int``, ver el ``json.loads(
json.dumps(...))`` de ``_eval_tax_amount_formula``). La conversión de
frontera vive aquí, no en ``account_tax.py`` — es plomería de integración
entre dos motores con contrato numérico distinto, no un símbolo propio de
la referencia ``account_tax_python``.
"""
from decimal import Decimal

from exceptions import ValidationError
from tools.translate import _

from addons.account.models.account_tax import AccountTax, AccountTaxQuerySet

#: Comportamiento original, capturado una única vez al importar este módulo
#: (ver el docstring de arriba — es el equivalente funcional de ``super()``).
_base_eval_tax_amount_fixed_amount = AccountTax._eval_tax_amount_fixed_amount


def _eval_tax_amount_fixed_amount(self, batch, raw_base, evaluation_context):
    """≙ ``_eval_tax_amount_fixed_amount`` (EXTENDS 'account' en la
    referencia). Despacha a la fórmula si ``amount_type == 'code'``; si no,
    delega en el comportamiento base capturado arriba.
    """
    if self.amount_type != 'code':
        return _base_eval_tax_amount_fixed_amount(
            self, batch, raw_base, evaluation_context)

    formula_record = getattr(self, 'formula_record', None)
    if formula_record is None:
        raise ValidationError(_(
            'El impuesto «%(nombre)s» usa amount_type=code sin un registro '
            'account_tax_python.AccountTaxFormula vinculado.'
        ) % {'nombre': self.name})

    # Frontera Decimal (motor de account) → float (fórmula, JSON-primitivo).
    # Ver la divergencia declarada en el docstring del módulo.
    float_context = {
        'price_unit': float(evaluation_context['price_unit']),
        'quantity': float(evaluation_context['quantity']),
        'product': evaluation_context.get('product', {}),
        'uom': evaluation_context.get('uom', {}),
    }
    resultado = formula_record._eval_tax_amount_formula(
        float(raw_base), float_context)
    return Decimal(str(resultado))


def _eval_taxes_computation_prepare_product_fields(self):
    """≙ ``_eval_taxes_computation_prepare_product_fields`` (EXTENDS
    'account'). Sin ``super()`` real que llamar (no existía antes): arranca
    en ``set()``, igual que la base Odoo que la referencia extiende.
    """
    field_names = set()
    for tax in self:
        if tax.amount_type != 'code':
            continue
        formula_record = getattr(tax, 'formula_record', None)
        if formula_record is not None:
            field_names.update(
                formula_record.formula_decoded_info['product_fields'])
    return field_names


def _eval_taxes_computation_prepare_product_uom_fields(self):
    """≙ ``_eval_taxes_computation_prepare_product_uom_fields`` (EXTENDS
    'account'). Mismo criterio que la de arriba, para uom.
    """
    field_names = set()
    for tax in self:
        if tax.amount_type != 'code':
            continue
        formula_record = getattr(tax, 'formula_record', None)
        if formula_record is not None:
            field_names.update(
                formula_record.formula_decoded_info['product_uom_fields'])
    return field_names


def apply_account_tax_python_extensions():
    """≙ ``_inherit = 'account.tax'`` de ``account_tax_python``.

    Se llama desde ``AccountTaxPythonConfig.ready()``, no al importar: en
    tiempo de import de este módulo el registro de apps aún no está
    poblado (``AppRegistryNotReady``).
    """
    if not hasattr(AccountTaxQuerySet,
                    '_eval_taxes_computation_prepare_product_fields'):
        AccountTaxQuerySet._eval_taxes_computation_prepare_product_fields = (
            _eval_taxes_computation_prepare_product_fields)
    if not hasattr(AccountTaxQuerySet,
                    '_eval_taxes_computation_prepare_product_uom_fields'):
        AccountTaxQuerySet._eval_taxes_computation_prepare_product_uom_fields = (
            _eval_taxes_computation_prepare_product_uom_fields)
    AccountTax._eval_tax_amount_fixed_amount = _eval_tax_amount_fixed_amount
