"""El saneo del campo ``Html``.

≙ ``odoo19c: odoo/orm/fields_textual.py:545-702``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
html-field-sanitize.md``.
"""
from types import SimpleNamespace
from unittest import mock

import pytest

import fields
from addons.account.models.account_payment_term import AccountPaymentTerm
from addons.base.models.ir_actions import ServerActionHistoryWizard
from addons.hr.models.hr_job import HrJob
from addons.mail.models.mail_message import MailMessage
from addons.mail.models.mail_template import MailTemplate
from addons.mass_mailing.models.mailing_mailing import MailingMailing
from addons.website.models.website import Website
from exceptions import UserError
from orm.fields_textual import Html

EVIL = '<p onclick="steal()">hola<script>alert(1)</script></p>'


def _field(**kwargs):
    field = fields.Html(**kwargs)
    field.set_attributes_from_name('body')
    return field


def test_the_source_defaults():
    field = _field()
    assert field.sanitize is True
    assert field.sanitize_overridable is False
    assert field.sanitize_tags is True
    assert field.sanitize_attributes is True
    assert field.sanitize_style is False
    assert field.sanitize_form is True
    assert field.sanitize_conditional_comments is True
    assert field.sanitize_output_method == 'html'
    assert field.strip_style is False
    assert field.strip_classes is False
    assert (Html.type, Html._column_type) == ('html', ('text', 'text'))


def test_email_outgoing_is_a_shortcut():
    field = _field(sanitize='email_outgoing')
    assert field.sanitize is True
    assert field.sanitize_tags is False
    assert field.sanitize_attributes is False
    assert field.sanitize_conditional_comments is False
    assert field.sanitize_output_method == 'xml'


def test_an_explicit_option_wins_over_the_shortcut():
    field = _field(sanitize='email_outgoing', sanitize_output_method='html')
    assert field.sanitize_output_method == 'html'


def test_the_related_and_description_properties_read_the_options():
    field = _field(sanitize_style=True, strip_classes=True)
    assert field._related_sanitize_style is True
    assert field._description_sanitize_style is True
    assert field._related_strip_classes is True
    assert field._description_strip_classes is True


def test_convert_sanitizes():
    assert _field()._convert(EVIL, None, True) == '<p>hola</p>'


def test_convert_keeps_the_value_without_sanitize_or_validate():
    assert _field(sanitize=False)._convert(EVIL, None, True) == EVIL
    assert _field()._convert(EVIL, None, False) == EVIL


def test_convert_maps_false_and_none_to_none():
    assert _field()._convert(False, None, True) is None
    assert _field()._convert(None, None, True) is None


def test_convert_to_cache_and_to_column_sanitize():
    field = _field()
    assert field.convert_to_cache(EVIL, None) == '<p>hola</p>'
    assert field.convert_to_column(EVIL, None) == '<p>hola</p>'


def test_the_static_shortcuts():
    assert str(Html.escape('<b>')) == '&lt;b&gt;'
    assert Html.is_empty('<p><br></p>') is True
    assert Html.from_plaintext('a') == '<p>a</p>'
    assert Html.to_plaintext('<p>a</p>') == 'a'


def test_an_overridable_field_refuses_restricted_content_to_a_user():
    field = _field(sanitize_overridable=True)
    record = SimpleNamespace(body='<p onclick="x">hola</p>',
                             _description='Prueba')
    with mock.patch('orm.fields_textual._user_has_group', return_value=False):
        with pytest.raises(UserError):
            field._convert('<p>nuevo</p>', record, True)


def test_an_overridable_field_lets_the_override_group_write_raw():
    field = _field(sanitize_overridable=True)
    record = SimpleNamespace(body='', _description='Prueba')
    with mock.patch('orm.fields_textual._user_has_group', return_value=True):
        assert field._convert(EVIL, record, True) == EVIL


@pytest.mark.django_db
def test_a_plain_model_sanitizes_on_save():
    term = AccountPaymentTerm.objects.create(name='Plazo', note=EVIL)
    term.refresh_from_db()
    assert term.note == '<p>hola</p>'


@pytest.mark.parametrize('model, name, options', [
    (Website, 'custom_code_head', {'sanitize': False}),
    (Website, 'custom_code_footer', {'sanitize': False}),
    (Website, 'robots_txt', {'sanitize': False}),
    (MailMessage, 'body', {'sanitize_style': True}),
    (MailTemplate, 'body_html', {'sanitize': True, 'sanitize_tags': False,
                                 'sanitize_output_method': 'xml'}),
    (MailingMailing, 'body_html', {'sanitize': True,
                                   'sanitize_tags': False}),
    (HrJob, 'description', {'sanitize_attributes': False}),
    (ServerActionHistoryWizard, 'code_diff', {'sanitize_tags': False}),
])
def test_the_declarations_carry_the_source_options(model, name, options):
    field = model._meta.get_field(name)
    for option, value in options.items():
        assert getattr(field, option) == value, option
