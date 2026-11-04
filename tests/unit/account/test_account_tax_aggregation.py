"""La agregación de detalles de impuestos por clave de agrupación.

≙ ``_aggregate_base_line_tax_details``, ``_aggregate_base_lines_tax_details``
y ``_aggregate_base_lines_aggregated_values`` (``odoo19c:
addons/account/models/account_tax.py:2512-2712``, LGPL-3). Las tres leen la
estructura que deja ``_round_base_lines_tax_details`` en cada ``base_line``;
cada caso la construye con las claves que el docstring de la fuente declara,
y cubre una rama: sin impuestos, clave de diccionario, montos manuales de
cada tipo, inversión del sujeto pasivo y la suma sobre el documento.
"""

from decimal import Decimal as D

import pytest

from addons.account.models import AccountTax
from tools.misc import frozendict

pytestmark = pytest.mark.unit


class _Tax:
    def __init__(self, pk):
        self.id = pk


def _tax_data(pk, base, tax, reverse=False):
    return {
        'tax': _Tax(pk), 'is_reverse_charge': reverse,
        'base_amount_currency': base, 'raw_base_amount_currency': base + 0.004,
        'base_amount': base * 2, 'raw_base_amount': base * 2 + 0.004,
        'tax_amount_currency': tax, 'raw_tax_amount_currency': tax + 0.001,
        'tax_amount': tax * 2, 'raw_tax_amount': tax * 2 + 0.001,
    }


def _base_line(taxes_data, manual_tax_amounts=None, **manual):
    line = {
        'tax_details': {
            'total_excluded_currency': 100.0,
            'delta_total_excluded_currency': 0.5,
            'raw_total_excluded_currency': 100.25,
            'total_excluded': 200.0, 'delta_total_excluded': 1.0,
            'raw_total_excluded': 200.5,
            'taxes_data': taxes_data,
        },
        'manual_tax_amounts': manual_tax_amounts,
        'manual_total_excluded_currency': None,
        'manual_total_excluded': None,
    }
    line.update(manual)
    return line


def _by_tax(base_line, tax_data):
    return {'tax': tax_data and tax_data['tax'].id}


def test_a_line_without_taxes_groups_under_the_function_of_none():
    line = _base_line([])
    calls = []

    def grouping(base_line, tax_data):
        calls.append(tax_data)
        return 'none'

    result = AccountTax._aggregate_base_line_tax_details(line, grouping)
    assert calls == [None]
    values = result['none']
    assert values['total_excluded_currency'] == 100.5
    assert values['raw_total_excluded_currency'] == 100.25
    assert values['target_total_excluded_currency'] == 100.25
    assert values['base_amount'] == 201.0
    assert values['raw_base_amount'] == 200.5
    assert values['tax_amount'] == 0.0
    assert values['taxes_data'] == []


def test_a_dict_key_becomes_a_frozendict_and_taxes_add_up():
    line = _base_line([_tax_data(1, 50.0, 8.0), _tax_data(1, 50.0, 8.0),
                       _tax_data(2, 100.0, 16.0)])
    result = AccountTax._aggregate_base_line_tax_details(line, _by_tax)
    assert set(result) == {frozendict({'tax': 1}), frozendict({'tax': 2})}
    one = result[frozendict({'tax': 1})]
    assert one['grouping_key'] == frozendict({'tax': 1})
    assert one['base_amount_currency'] == 50.0
    assert one['tax_amount_currency'] == 16.0
    assert one['raw_tax_amount_currency'] == pytest.approx(16.002)
    assert one['target_tax_amount_currency'] == pytest.approx(16.002)
    assert len(one['taxes_data']) == 2


def test_manual_amounts_set_the_targets():
    line = _base_line(
        [_tax_data(1, 50.0, 8.0)],
        manual_tax_amounts={'1': {'base_amount_currency': 49.0,
                                  'tax_amount_currency': 7.0}},
        manual_total_excluded_currency=99.0,
    )
    values = AccountTax._aggregate_base_line_tax_details(line, _by_tax)[
        frozendict({'tax': 1})]
    assert values['target_total_excluded_currency'] == 99.0
    # Sin monto manual en moneda local, la meta local es el monto redondeado.
    assert values['target_total_excluded'] == 201.0
    assert values['target_base_amount_currency'] == 49.0
    assert values['target_base_amount'] == 100.0
    assert values['target_tax_amount_currency'] == 7.0
    assert values['target_tax_amount'] == 16.0


def test_a_reverse_charge_tax_negates_its_manual_amount():
    line = _base_line([_tax_data(1, 50.0, -8.0, reverse=True)],
                      manual_tax_amounts={'1': {'tax_amount': 16.0}})
    values = AccountTax._aggregate_base_line_tax_details(line, _by_tax)[
        frozendict({'tax': 1})]
    assert values['target_tax_amount'] == -16.0


def test_the_document_sums_each_key_across_lines():
    first = _base_line([_tax_data(1, 50.0, 8.0)])
    second = _base_line([_tax_data(1, 30.0, 4.8), _tax_data(2, 10.0, 1.0)])
    per_line = AccountTax._aggregate_base_lines_tax_details(
        [first, second], _by_tax)
    assert [line for line, _ in per_line] == [first, second]
    total = AccountTax._aggregate_base_lines_aggregated_values(per_line)
    one = total[frozendict({'tax': 1})]
    assert one['base_amount_currency'] == 80.0
    assert one['tax_amount_currency'] == pytest.approx(12.8)
    assert one['total_excluded_currency'] == 201.0
    assert one['grouping_key'] == frozendict({'tax': 1})
    assert [line for line, _ in one['base_line_x_taxes_data']] == [
        first, second]
    two = total[frozendict({'tax': 2})]
    assert two['base_amount_currency'] == 10.0
    assert two['base_line_x_taxes_data'] == [
        (second, [second['tax_details']['taxes_data'][1]])]


def test_the_amounts_of_the_engine_are_decimal_and_add_up():
    """El motor de este árbol entrega ``Decimal``; la suma por clave no puede
    partir de un ``0.0`` de ``float``, que con ``Decimal`` es ``TypeError``."""

    def decimal_tax_data(pk):
        data = _tax_data(pk, 50.0, 8.0)
        return {key: (D(str(value)) if isinstance(value, float) else value)
                for key, value in data.items()}

    line = _base_line([decimal_tax_data(1)])
    for key in ('total_excluded_currency', 'delta_total_excluded_currency',
                'raw_total_excluded_currency', 'total_excluded',
                'delta_total_excluded', 'raw_total_excluded'):
        line['tax_details'][key] = D(str(line['tax_details'][key]))
    per_line = AccountTax._aggregate_base_lines_tax_details([line], _by_tax)
    total = AccountTax._aggregate_base_lines_aggregated_values(per_line)
    values = total[frozendict({'tax': 1})]
    assert values['tax_amount_currency'] == D('8.0')
    assert isinstance(values['tax_amount_currency'], D)
