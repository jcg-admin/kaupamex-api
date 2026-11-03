"""El reparto de un delta de redondeo entre factores.

≙ ``_normalize_target_factors`` y ``_distribute_delta_amount_smoothly``
(``odoo19c: addons/account/models/account_tax.py:1824-1893``, LGPL-3). El
redondeo de base-lines los usa para repartir los céntimos que la suma de
líneas redondeadas pierde frente al total redondeado.
"""

import pytest

from addons.account.models import AccountTax

pytestmark = pytest.mark.unit


def _factors(*values):
    return [{'factor': value} for value in values]


def test_the_source_example():
    """El ejemplo del docstring de la fuente: 0.03 con tres decimales
    sobre 0.4, 0.3 y 0.3 da 0.012, 0.009 y 0.009."""
    amounts = AccountTax._distribute_delta_amount_smoothly(
        3, 0.03, _factors(0.4, 0.3, 0.3))
    assert amounts == pytest.approx([0.012, 0.009, 0.009])


def test_the_residual_cent_goes_to_the_biggest_factor_first():
    """Dos céntimos sobre 1, 3 y 1 (0.6, 0.2, 0.2 normalizados): el reparto
    por factor da ``round(0.6 * 2) = 1`` al mayor y cero a los otros dos, y
    el céntimo que sobra también va al mayor."""
    amounts = AccountTax._distribute_delta_amount_smoothly(
        2, 0.02, _factors(1, 3, 1))
    assert amounts == pytest.approx([0.0, 0.02, 0.0])


def test_a_negative_delta_keeps_its_sign():
    amounts = AccountTax._distribute_delta_amount_smoothly(
        2, -0.03, _factors(2, 1))
    assert amounts == pytest.approx([-0.02, -0.01])


def test_a_zero_delta_distributes_nothing():
    assert AccountTax._distribute_delta_amount_smoothly(
        2, 0.004, _factors(1, 1)) == [0.0, 0.0]


def test_normalized_factors_sum_one_and_come_sorted():
    normalized = AccountTax._normalize_target_factors(_factors(1, -3, 0))
    assert [index for index, _ in normalized] == [1, 0, 2]
    assert [factor for _, factor in normalized] == pytest.approx(
        [0.75, 0.25, 0.0])


def test_null_factors_share_equally():
    normalized = AccountTax._normalize_target_factors(_factors(0, 0))
    assert [factor for _, factor in normalized] == [0.5, 0.5]
