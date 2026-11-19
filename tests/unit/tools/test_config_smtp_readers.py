"""Lectores SMTP de ``tools.config``.

≙ ``odoo19c: odoo/tools/config.py:350-366``.
"""
from django.test import override_settings

from tools import config

# Los valores por defecto que la fuente declara para cada opción.
SOURCE_DEFAULTS = {
    'email_from': '',
    'from_filter': '',
    'smtp_server': 'localhost',
    'smtp_port': 25,
    'smtp_ssl': False,
    'smtp_user': '',
    'smtp_password': '',
    'smtp_ssl_certificate_filename': '',
    'smtp_ssl_private_key_filename': '',
}


@override_settings(
    DEFAULT_FROM_EMAIL='', EMAIL_HOST='', EMAIL_PORT=None, EMAIL_USE_TLS=False,
    EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='', EMAIL_SSL_CERTFILE=None,
    EMAIL_SSL_KEYFILE=None,
)
def test_unset_settings_fall_back_to_source_defaults():
    got = {name: getattr(config, name)() for name in SOURCE_DEFAULTS}
    assert got == SOURCE_DEFAULTS


@override_settings(
    DEFAULT_FROM_EMAIL='a@x.mx', EMAIL_FROM_FILTER='x.mx',
    EMAIL_HOST='smtp.x.mx',
    EMAIL_PORT=587, EMAIL_USE_TLS=True, EMAIL_HOST_USER='u',
    EMAIL_HOST_PASSWORD='p', EMAIL_SSL_CERTFILE='/c.pem',
    EMAIL_SSL_KEYFILE='/k.pem',
)
def test_declared_settings_are_read():
    assert config.email_from() == 'a@x.mx'
    assert config.from_filter() == 'x.mx'
    assert config.smtp_server() == 'smtp.x.mx'
    assert config.smtp_port() == 587
    assert config.smtp_ssl() is True
    assert config.smtp_user() == 'u'
    assert config.smtp_password() == 'p'
    assert config.smtp_ssl_certificate_filename() == '/c.pem'
    assert config.smtp_ssl_private_key_filename() == '/k.pem'
