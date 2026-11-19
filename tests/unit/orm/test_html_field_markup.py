"""El campo ``Html`` entrega ``Markup`` al leerse.

≙ ``Html.convert_to_record`` y ``Html.convert_to_read`` (``odoo19c:
odoo/orm/fields_textual.py:684-694``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
html-field-markup.md``.
"""
import pytest
from markupsafe import Markup

import fields
from addons.account.models.account_payment_term import AccountPaymentTerm


def _field():
    field = fields.Html()
    field.set_attributes_from_name('body')
    return field


def test_convert_to_record_wraps_in_markup():
    value = _field().convert_to_record('<p>hola</p>', None)
    assert type(value) is Markup
    assert value == '<p>hola</p>'


def test_convert_to_record_decodes_bytes():
    value = _field().convert_to_record(b'<p>hola</p>', None)
    assert type(value) is Markup
    assert value == '<p>hola</p>'


def test_an_empty_value_stays_falsy():
    assert _field().convert_to_record(None, None) is False
    assert _field().convert_to_record('', None) == ''
    assert type(_field().convert_to_record('', None)) is not Markup


def test_convert_to_read_wraps_in_markup():
    value = _field().convert_to_read('<p>hola</p>', None)
    assert type(value) is Markup


@pytest.mark.django_db
def test_reading_a_stored_html_column_gives_markup():
    term = AccountPaymentTerm.objects.create(name='Plazo', note='<p>a</p>')
    term.refresh_from_db()
    assert type(term.note) is Markup
    assert term.note == '<p>a</p>'
