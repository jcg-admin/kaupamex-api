"""La superficie del modelo ``ir.mail_server`` que la fuente declara.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``:
``_compute_smtp_authentication_info`` (``:204-220``),
``_check_smtp_ssl_files`` (``:222-229``) y ``_onchange_encryption``
(``:979-990``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 3e.
"""
import pytest

from addons.base.models.ir_mail_server import IrMailServer
from exceptions import UserError
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('method, start', [
    ('login', 'Connect to your server through your usual username'),
    ('certificate', 'Authenticate by using SSL certificates'),
    ('cli', 'Use the SMTP configuration set in the "Command Line'),
])
def test_the_authentication_info_is_the_source_text(method, start):
    server = IrMailServer(smtp_authentication=method)
    assert str(server.smtp_authentication_info).startswith(start)


def test_an_unknown_method_has_no_information():
    assert IrMailServer(smtp_authentication='')\
        .smtp_authentication_info is False


def _certificate_server(**values):
    with sudo():
        return IrMailServer.create({
            'name': 'cert', 'smtp_host': 'smtp.kaupamex.mx',
            'smtp_authentication': 'certificate',
            'smtp_encryption': 'starttls', **values})


def test_a_certificate_server_needs_its_private_key():
    with pytest.raises(UserError) as error:
        _certificate_server(smtp_ssl_certificate=b'Y2VydA==')
    assert str(error.value) == 'SSL private key is missing for cert.'


def test_a_certificate_server_needs_its_certificate():
    with pytest.raises(UserError) as error:
        _certificate_server(smtp_ssl_private_key=b'a2V5')
    assert str(error.value) == 'SSL certificate is missing for cert.'


def test_ssl_suggests_the_ssl_port():
    server = IrMailServer(smtp_encryption='ssl', smtp_port=25)
    assert server._onchange_encryption() == {}
    assert server.smtp_port == 465


def test_any_other_encryption_resets_the_port_to_25():
    server = IrMailServer(smtp_encryption='starttls', smtp_port=587)
    assert server._onchange_encryption() == {}
    assert server.smtp_port == 25
