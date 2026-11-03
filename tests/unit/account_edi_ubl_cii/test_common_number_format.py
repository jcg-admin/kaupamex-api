"""Formato numérico de ``account.edi.common`` — ≙ ``odoo19c:
addons/account_edi_ubl_cii/models/account_edi_common.py`` (``FloatFmt``,
``format_float``, ``_import_prepaid_amount``).

``float_repr`` y ``formatLang`` se importan de ``src/tools``; antes eran
copias locales, y la de ``float_repr`` no ponía a cero.
"""

import pytest
from lxml import etree

from addons.account_edi_ubl_cii.models.account_edi_common import (
    AccountEdiCommon,
    FloatFmt,
)
from orm.environments import Environment
from orm.utils import SUPERUSER_ID


def test_format_float_writes_a_null_amount_without_sign():
    """El caso que la copia local fallaba: ``-0.001`` a dos decimales."""
    assert AccountEdiCommon.format_float(-0.001, 2) == '0.00'
    assert AccountEdiCommon.format_float(12.345, 2) == '12.35'
    assert AccountEdiCommon.format_float(None, 2) is None


def test_float_fmt_keeps_between_min_and_max_places():
    assert str(FloatFmt(1.5, min_dp=2)) == '1.50'
    assert str(FloatFmt(1.25, min_dp=1, max_dp=4)) == '1.25'
    assert str(FloatFmt(-0.0001, min_dp=2, max_dp=3)) == '0.00'


@pytest.mark.django_db
def test_prepaid_amount_is_reported_with_format_lang():
    class Currency:
        decimal_places = 2
        symbol = '$'
        position = 'before'

        @staticmethod
        def is_zero(amount):
            return abs(amount) < 0.005

    class Invoice:
        currency = Currency()

    tree = etree.fromstring(
        b'<Invoice><PrepaidAmount>1234.5</PrepaidAmount></Invoice>')
    with Environment(None, SUPERUSER_ID, {}):
        logs = AccountEdiCommon._import_prepaid_amount(
            Invoice(), tree, './/PrepaidAmount', 1)
    assert [str(log) for log in logs] == [
        'A payment of $\N{NO-BREAK SPACE}1,234.50 was detected.']
