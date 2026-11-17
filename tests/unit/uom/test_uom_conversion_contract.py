"""Contrato de conversión de ``uom.uom`` y su frontera con ``Decimal``.

Referencia: ``odoo19c: addons/uom/models/uom_uom.py:147-203``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/``
``uom-decimal-boundary.md``.
"""

from decimal import Decimal

import pytest

from addons.base.models import DecimalPrecision
from addons.uom.models import Uom

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def units():
    precision, _ = DecimalPrecision.objects.get_or_create(
        name='Product Unit', defaults={'digits': 2})
    precision.digits = 2
    precision.save()
    gram = Uom.objects.create(name='g', relative_factor=1.0)
    kgm = Uom.objects.create(
        name='kg', relative_factor=1000, relative_uom_id=gram)
    unit = Uom.objects.create(name='Units', relative_factor=1.0)
    dozen = Uom.objects.create(
        name='Dozens', relative_factor=12, relative_uom_id=unit)
    return {'gram': gram, 'kgm': kgm, 'unit': unit, 'dozen': dozen}


@pytest.mark.parametrize('qty, expected', [
    (2.0, 24.0),
    (-2.0, -24.0),
    (0.5, 6.0),
])
def test_float_quantities_keep_their_type(units, qty, expected):
    result = units['dozen']._compute_quantity(qty, units['unit'])
    assert result == expected
    assert isinstance(result, float)


@pytest.mark.parametrize('qty, expected', [
    (Decimal('2'), Decimal('24.0')),
    (Decimal('-2'), Decimal('-24.0')),
    (Decimal('0.5'), Decimal('6.0')),
])
def test_decimal_quantities_convert_and_keep_their_type(
        units, qty, expected):
    result = units['dozen']._compute_quantity(qty, units['unit'])
    assert result == expected
    assert isinstance(result, Decimal)


def test_a_decimal_in_the_same_unit_is_rounded_and_stays_decimal(units):
    result = units['unit']._compute_quantity(
        Decimal('1.234'), units['unit'])
    assert result == Decimal('1.24')
    assert isinstance(result, Decimal)


def test_rounding_follows_the_requested_method(units):
    assert units['gram']._compute_quantity(
        Decimal('1234'), units['kgm'], rounding_method='HALF-UP',
    ) == Decimal('1.23')
    assert units['gram']._compute_quantity(
        Decimal('1234'), units['kgm']) == Decimal('1.24')


def test_without_rounding_the_raw_factor_ratio_is_returned(units):
    result = units['gram']._compute_quantity(
        Decimal('1234'), units['kgm'], round=False)
    assert result == Decimal('1.234')


def test_zero_returns_the_same_object(units):
    zero = Decimal('0.0000')
    assert units['dozen']._compute_quantity(zero, units['unit']) is zero


def test_without_destination_only_the_factor_is_applied(units):
    # ``if to_unit:`` de la fuente: sin destino no se divide ni se redondea.
    result = units['dozen']._compute_quantity(Decimal('1.5'), None)
    assert result == Decimal('18.0')
    assert isinstance(result, Decimal)


def test_unrelated_roots_convert_by_absolute_factor_without_raising(units):
    # La 19 no tiene uom.category: raise_if_failure se declara y no se usa.
    # 12 / 1000 = 0.012, redondeado hacia arriba a 0.01 de paso: 0.02.
    assert units['dozen']._compute_quantity(
        1.0, units['kgm'], raise_if_failure=True) == 0.02
    assert units['dozen']._compute_quantity(
        1.0, units['kgm'], raise_if_failure=False) == 0.02


def test_decimal_prices_convert_and_keep_their_type(units):
    result = units['unit']._compute_price(Decimal('2.5'), units['dozen'])
    assert result == Decimal('30.0')
    assert isinstance(result, Decimal)
    assert units['unit']._compute_price(2.5, units['dozen']) == 30.0
