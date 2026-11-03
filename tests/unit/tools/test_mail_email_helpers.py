"""Ayudantes de direcciones de ``tools.mail`` (``odoo19c: odoo/tools/mail.py:
728-1068``). Los ejemplos de ``email_anonymize`` son los doctests de la fuente."""

import email.message
import re

from tools import mail


def test_generate_tracking_message_id_is_a_unique_header_value():
    first = mail.generate_tracking_message_id(42)
    assert re.fullmatch(r'<\d{15}\.\d+\.\d{15}-openerp-42@[^>]+>', first)
    assert first != mail.generate_tracking_message_id(42)


def test_email_split_and_format_formats_each_address():
    text = '"Ana" <ana@x.mx>, beto@x.mx'
    assert mail.email_split_and_format(text) == ['"Ana" <ana@x.mx>', 'beto@x.mx']


def test_the_normalizing_variants_lower_the_address():
    text = 'Ana <ANA@X.MX>'
    assert mail.email_split_and_normalize(text) == [('Ana', 'ana@x.mx')]
    assert mail.email_split_and_format_normalize(text) == ['"Ana" <ana@x.mx>']


def test_email_anonymize_matches_the_source_doctests():
    assert mail.email_anonymize('admin@example.com') == 'a****@example.com'
    assert mail.email_anonymize('portal@example.com') == 'p***al@example.com'
    assert mail.email_anonymize('portal@example.com', redact_domain=True) == 'p***al@e******.com'
    assert mail.email_anonymize('') == ''


def test_url_domain_extract_drops_subdomains():
    assert mail.url_domain_extract('https://www.info.proximus.be/a') == 'proximus.be'
    assert mail.url_domain_extract('https://localhost') is False


def test_email_escape_char_escapes_like_patterns():
    assert mail.email_escape_char('a_b%c\\d') == 'a\\_b\\%c\\\\d'


def test_decode_message_header_joins_every_value():
    message = email.message.Message()
    message['References'] = '<a@x>'
    message['References'] = '<b@x>'
    assert mail.decode_message_header(message, 'References') == '<a@x> <b@x>'
    assert mail.decode_message_header(message, 'Missing') == ''


def test_encapsulate_email_keeps_the_old_name_on_the_new_address():
    assert mail.encapsulate_email('"Admin" <admin@gmail.com>', 'notifications@odoo.com') \
        == '"Admin" <notifications@odoo.com>'
    assert mail.encapsulate_email('admin@gmail.com', 'n@odoo.com') == '"admin" <n@odoo.com>'


def test_unfold_references_removes_folding_whitespace():
    assert mail.unfold_references('<a@\r\n x> <b@y>') == ['<a@x>', '<b@y>']
