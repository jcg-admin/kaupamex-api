"""``_check_default_from_not_used_by_users`` de ``mail.alias.domain``.

≙ ``odoo19c: addons/mail/models/mail_alias_domain.py:150,172,175-184``: un
dominio de alias no puede usar como remitente una dirección que ya ocupa un
servidor de correo personal.
"""
import pytest

from addons.base.models import ResUsers
from addons.base.models.ir_mail_server import IrMailServer
from addons.mail.models.mail_alias_domain import MailAliasDomain
from exceptions import UserError
from orm.environments import sudo

pytestmark = pytest.mark.django_db


def _personal_server(email):
    owner = ResUsers.objects.create_user(login=email, password='x' * 12,
                                         name=email)
    with sudo():
        return IrMailServer.create({
            'name': email, 'smtp_host': 'localhost', 'from_filter': email,
            'smtp_user': email, 'owner_user_id': owner})


def test_creating_a_domain_on_a_personal_address_is_refused():
    _personal_server('avisos@personal.mx')
    with pytest.raises(UserError, match='personal mail server'):
        MailAliasDomain.objects.create(name='personal.mx',
                                       default_from='avisos')
    assert not MailAliasDomain.objects.filter(name='personal.mx').exists()


def test_changing_the_sender_to_a_personal_address_is_refused():
    _personal_server('avisos@cambio.mx')
    domain = MailAliasDomain.objects.create(name='cambio.mx',
                                            default_from='otro')
    domain.default_from = 'avisos'
    with pytest.raises(UserError, match='personal mail server'):
        domain.save()
    assert MailAliasDomain.objects.get(pk=domain.pk).default_from == 'otro'


def test_a_public_server_does_not_block_the_sender():
    with sudo():
        IrMailServer.create({'name': 'publico', 'smtp_host': 'localhost',
                             'from_filter': 'avisos@publico.mx'})
    domain = MailAliasDomain.objects.create(name='publico.mx',
                                            default_from='avisos')
    assert domain.pk
