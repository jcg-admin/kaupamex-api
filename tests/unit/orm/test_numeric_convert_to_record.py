"""La ausencia de un número se lee como cero, como en la referencia.

≙ ``odoo19c: odoo/orm/fields_numeric.py:171-172`` (``Float``) y
``:282-283`` (``Monetary``): ``convert_to_record`` devuelve ``value or 0.0``.
El ``Integer`` ya lo hacía (``:41-42``); ``FloatField`` y ``DecimalField``
caían en el conversor genérico, que entregaba ``False`` por ``None``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
new-line-recompute-flow.md``.
"""
from decimal import Decimal

import pytest
from django.db import models


@pytest.mark.parametrize('field, empty, zero', [
    (models.FloatField(), None, 0.0),
    (models.FloatField(), False, 0.0),
    (models.DecimalField(max_digits=12, decimal_places=2), None, Decimal(0)),
    (models.DecimalField(max_digits=12, decimal_places=2), False, Decimal(0)),
])
def test_an_absent_number_reads_as_zero(field, empty, zero):
    value = field.convert_to_record(empty, None)
    assert value == zero
    assert type(value) is type(zero)


@pytest.mark.parametrize('field, value', [
    (models.FloatField(), 2.5),
    (models.DecimalField(max_digits=12, decimal_places=2), Decimal('7.10')),
])
def test_a_present_number_is_kept(field, value):
    assert field.convert_to_record(value, None) == value


def test_a_primary_key_keeps_the_generic_conversion():
    """Control: el conversor del entero excluye la clave primaria; éste no
    toca ni ``AutoField`` ni ``CharField``."""
    assert models.AutoField(primary_key=True).convert_to_record(None, None) \
        is False
    assert models.CharField().convert_to_record(None, None) is False


def test_a_present_decimal_zero_keeps_its_scale():
    """``Decimal('0.00')`` es un cero presente, no una ausencia: conserva su
    escala, que el formato de un importe (``$0.00``) usa."""
    field = models.DecimalField(max_digits=12, decimal_places=2)
    value = field.convert_to_record(Decimal('0.00'), None)
    assert value.as_tuple().exponent == -2
