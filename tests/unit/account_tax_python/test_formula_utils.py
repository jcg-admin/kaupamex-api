"""Validador/normalizador de fórmulas — porte de los tres tests de AST de
``odoo19c: addons/account_tax_python/tests/test_taxes_computation.py``
(``test_invalid_formula``, ``test_ast_transformer_normalizes``,
``test_ast_validator``), adaptados a la firma sin ``env`` de este árbol.

No requieren DB: ``check_formula``/``normalize_formula`` son AST puro, y
``_check_and_normalize_formula`` sólo introspecciona clases Django ya
importadas (``ProductProduct._meta.get_field``) — sin tocar la base.
"""
import pytest

from addons.account_tax_python.models.account_tax import AccountTaxFormula
from addons.account_tax_python.tools.formula_utils import (
    check_formula,
    normalize_formula,
)
from exceptions import ValidationError

pytestmark = [pytest.mark.unit]


# -- test_ast_validator (odoo19c: :198-241) ---------------------------------

TO_FAIL_AST_VALIDATOR = [
    # sin atributos: el transformer ya reescribió a subíndice antes de
    # validar, así que no se aceptan Attribute en este paso.
    "product.field",
    "isinstance",
    "product.env",
    "(None for _ in ()).gi_frame.f_builtins['__import__']",
    # sólo los nodos de la whitelist (nada de tuplas, sets, dicts, listas…)
    "1,",
    "product,",
    "min(1, 2),",
    "()",
    "{}",
    "[]",
    "{1: product}",
    "{1, 2}",
    "[product]",
    "(None for _ in product)",
    # sólo subíndices de cadena sobre product/uom
    "product[None]",
    "product[1]",
    "product[:]",
    "not_product['field']",
    # sin llamadas arbitrarias
    "product['a_callable']()",
    "product()",
    "(min or max)(1, 2)",
    "isinstance(1, ())",
    # sin carga arbitraria de nombres
    "a",
    "__builtins__",
    "isinstance",
]


@pytest.mark.parametrize('formula', TO_FAIL_AST_VALIDATOR)
def test_ast_validator_rejects(formula):
    with pytest.raises(ValidationError):
        check_formula(formula)


# -- test_ast_transformer_normalizes (odoo19c: :170-196) --------------------

VALID_NORMALIZE_CASES = [
    (
        "((10_000 / product.__dunders__) * (product['shall'] - product[\"n0t\"] + ((product._pass)))) -.01",
        "10000 / product['__dunders__'] * (product['shall'] - product['n0t'] + product['_pass']) - 0.01",
        {"__dunders__", "shall", "n0t", "_pass"},
    ),
    (
        "-bob[eats(product . sandwich)] + +product. \\\nwith_fries_inside and product['IS_THE_WAY']",
        "-bob[eats(product['sandwich'])] + +product['with_fries_inside'] and product['IS_THE_WAY']",
        {"sandwich", "with_fries_inside", "IS_THE_WAY"},
    ),
    (
        "(product.help_youself, product['with some']) if product[None] else product.tarte_al_djote['grault']",
        "(product['help_youself'], product['with some']) if product[None] else product['tarte_al_djote']['grault']",
        {"help_youself", "with some", "tarte_al_djote"},
    ),
]


@pytest.mark.parametrize(
    'formula,esperado_normalizado,campos_esperados', VALID_NORMALIZE_CASES)
def test_ast_transformer_normalizes(formula, esperado_normalizado, campos_esperados):
    normalizado, campos_accedidos = normalize_formula(formula)
    assert campos_accedidos['product.product'] == campos_esperados
    assert normalizado == esperado_normalizado


# -- test_invalid_formula (odoo19c: :141-168) --------------------------------
# ``product.product_tmpl_id`` de la referencia (campo relacional en Odoo) se
# adapta a ``product.product_tmpl`` — el nombre real del FK en este árbol
# (``ProductProduct.product_tmpl``, ver ``product/models/product_product.py``).
# Sigue siendo relacional: la razón del rechazo no cambia.

INVALID_FORMULAS = [
    'product.product_tmpl',       # sin campos relacionales
    'product.sudo()',             # no hay control de acceso que simular
    'tuple(1, 2, 3)',             # sólo min/max, ninguna otra llamada
    'set(1, 2, 3)',
    '[1, 2, 3]',
    '1,',
    '{1, 2}',
    '{1: 2}',
    '(i for _ in product)',
    '"test"',                     # las cadenas sólo se permiten en subíndices
    'product[min("volume", "price")]',
    'product()',
    'product[0]',
    'product[:10]',
    'product["field_that_does_not_exist"]',
    'product.field_that_does_not_exist',
    'product.ids',
    'product._fields',
    'product.env.cr',
    'range(1, 10)',
]


@pytest.mark.parametrize('formula', INVALID_FORMULAS)
def test_check_and_normalize_formula_rejects(formula):
    with pytest.raises(ValidationError):
        AccountTaxFormula._check_and_normalize_formula(formula)


# -- campos de producto/uom que SÍ existen y son serializables ---------------

def test_check_and_normalize_formula_accepts_product_volume():
    normalizado, campos = AccountTaxFormula._check_and_normalize_formula(
        'product.volume * quantity * 0.35')
    assert normalizado == "product['volume'] * quantity * 0.35"
    assert campos['product.product'] == {'volume'}


def test_check_and_normalize_formula_accepts_uom_relative_factor():
    normalizado, campos = AccountTaxFormula._check_and_normalize_formula(
        'uom.relative_factor')
    assert normalizado == "uom['relative_factor']"
    assert campos['uom.uom'] == {'relative_factor'}
