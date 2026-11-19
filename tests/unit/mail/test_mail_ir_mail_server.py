"""La extensión de ``ir.mail_server`` de ``mail``.

≙ ``odoo19c: addons/mail/models/ir_mail_server.py:10-106``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 5-1a.
"""
from types import SimpleNamespace
from unittest import mock

import pytest
from django.db import IntegrityError, transaction

from addons.base.models import ResUsers
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_mail_server import IrMailServer
from addons.mail.models.mail_alias_domain import MailAliasDomain
from orm.domains import Domain
from orm.environments import SUPERUSER_ID, Environment, sudo

pytestmark = pytest.mark.django_db


def _model():
    return Environment(uid=SUPERUSER_ID)['ir.mail_server']


def _server(**values):
    with sudo():
        return IrMailServer.create({
            'name': values.pop('name', 'smtp'), 'smtp_host': 'localhost',
            **values})


def _user(login):
    return ResUsers.objects.create_user(login=login, password='x' * 12,
                                        name=login)


def test_the_extension_declares_the_source_fields():
    fields = {f.name: f for f in IrMailServer._meta.get_fields()}
    assert fields['owner_user_id'].related_model is ResUsers
    assert 'owner_limit_time' in fields
    assert 'owner_limit_count' in fields
    assert IrMailServer._email_field == 'smtp_user'


def test_an_owner_has_at_most_one_server():
    names = [c.name for c in IrMailServer._meta.constraints]
    assert 'ir_mail_server_unique_owner_user_id' in names
    owner = _user('dueno@kaupamex.mx')
    _server(name='uno', owner_user_id=owner)
    with pytest.raises(IntegrityError), transaction.atomic():
        _server(name='dos', owner_user_id=owner)


def test_the_search_leaves_personal_servers_out():
    assert _model()._find_mail_server_allowed_domain() == Domain(
        'owner_user_id', '=', False)
    IrMailServer.objects.all().delete()
    _server(name='personal', from_filter='ana@kaupamex.mx',
            owner_user_id=_user('ana@kaupamex.mx'))
    public = _server(name='publico', from_filter='kaupamex.mx')
    with sudo():
        server, _sender = _model()._find_mail_server('ana@kaupamex.mx')
    assert server == public


def test_the_fallback_leaves_personal_servers_out():
    personal = _server(name='personal', owner_user_id=_user('b@kaupamex.mx'))
    public = _server(name='publico')
    with sudo():
        kept = _model()._filter_mail_servers_fallback(personal | public)
    assert kept == public


def test_the_company_sender_and_bounce_win():
    company = SimpleNamespace(bounce_email='rebote@kaupamex.mx',
                              default_from_email='avisos@kaupamex.mx')
    with mock.patch.object(Environment, 'company',
                           new_callable=mock.PropertyMock,
                           return_value=company):
        assert _model()._get_default_bounce_address() == 'rebote@kaupamex.mx'
        assert _model()._get_default_from_address() == 'avisos@kaupamex.mx'


def test_without_company_values_the_base_defaults_apply(settings):
    settings.DEFAULT_FROM_EMAIL = 'base@kaupamex.mx'
    company = SimpleNamespace(bounce_email='', default_from_email='')
    with mock.patch.object(Environment, 'company',
                           new_callable=mock.PropertyMock,
                           return_value=company):
        assert _model()._get_default_bounce_address() == 'base@kaupamex.mx'
        assert _model()._get_default_from_address() == 'base@kaupamex.mx'


def test_the_test_sender_prefers_a_complete_address():
    assert IrMailServer(
        from_filter='kaupamex.mx, ana@kaupamex.mx',
    )._get_test_email_from() == 'ana@kaupamex.mx'


def test_a_domain_filter_uses_the_matching_alias_domain_sender():
    MailAliasDomain.objects.create(name='kaupamex.mx', default_from='avisos')
    assert IrMailServer(
        from_filter='kaupamex.mx')._get_test_email_from() == (
        'avisos@kaupamex.mx')


def test_without_a_matching_alias_domain_the_sender_is_a_placeholder():
    MailAliasDomain.objects.filter(name='otra.mx').delete()
    assert IrMailServer(
        from_filter='otra.mx')._get_test_email_from() == 'odoo@otra.mx'


def test_the_personal_limit_defaults_to_30():
    SystemParameter.objects.filter(
        key='mail.server.personal.limit.minutes').delete()
    assert IrMailServer()._get_personal_mail_servers_limit() == 30
    SystemParameter.set_param('mail.server.personal.limit.minutes', '10')
    assert IrMailServer()._get_personal_mail_servers_limit() == 10
