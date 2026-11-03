"""Los cuatro de presentación de ``tools.float_utils`` — ≙ ``odoo19c:
odoo/tools/float_utils.py:262-347`` y ``test_float_split_05``
(``odoo/addons/base/tests/test_float.py:218-243``), con sus casos verbatim.
La moneda de la fuente es ``base.EUR`` (``rounding`` 0.01): dos decimales.
"""

import json

import pytest

from tools.float_utils import (
    float_repr,
    float_split,
    float_split_str,
    json_float_round,
)


@pytest.mark.parametrize('value, expected, digits', [
    (2.674, ('2', '67'), 2),
    (2.675, ('2', '68'), 2),
    (-2.675, ('-2', '68'), 2),
    (0.001, ('0', '00'), 2),
    (-0.001, ('0', '00'), 2),
    (42, ('42', '00'), 2),
    (0.1, ('0', '10'), 2),
    (13.0, ('13', ''), 0),
])
def test_float_split_str(value, expected, digits):
    assert float_split_str(value, precision_digits=digits) == expected


@pytest.mark.parametrize('value, expected, digits', [
    (2.674, (2, 67), 2),
    (2.675, (2, 68), 2),
    (-2.675, (-2, 68), 2),
    (0.001, (0, 0), 2),
    (-0.001, (0, 0), 2),
    (42, (42, 0), 2),
    (0.1, (0, 10), 2),
    (13.0, (13, 0), 0),
])
def test_float_split(value, expected, digits):
    assert float_split(value, precision_digits=digits) == expected


def test_float_repr_writes_a_zero_without_its_sign():
    """El paso a cero de la fuente: un valor nulo a esa precisión se escribe
    ``0.00``, no ``-0.00``."""
    assert float_repr(-0.001, 2) == '0.00'
    assert float_repr(-0.0, 2) == '0.00'
    assert float_repr(123456789.1234, 4) == '123456789.1234'


def test_json_float_round_serializes_the_rounded_repr():
    assert json_float_round(3.17499999, 3) == 3.175
    assert json.dumps(json_float_round(2.675, 2)) == '2.68'
