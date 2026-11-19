"""El servidor saliente personal de ``res.users`` (ítem A de ``mail``).

≙ ``odoo19c: addons/mail/models/res_users.py:50-68,130-149,165-167,545-660``
y ``addons/mail/models/ir_mail_server.py:91-99``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 5-1b.
"""
import pytest

from addons.base.models import ResUsers
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_mail_server import IrMailServer
from addons.base.models.ir_model import IrModelData
from addons.mail.models.mail_alias_domain import MailAliasDomain
from addons.mail.models.res_users import EXTERNAL_SERVER_PARAM
from exceptions import UserError
from orm.environments import SUPERUSER_ID, Environment, sudo, user_scope

pytestmark = pytest.mark.django_db


def _user(login, email=None, internal=True):
    user = ResUsers.objects.create_user(login=login, password='x' * 12,
                                        name=login)
    if email is not None:
        user.email = email
        user.save()
    if internal:
        user.group_ids.add(IrModelData.ref('base.group_user'))
    return user


def _server(**values):
    with sudo():
        return IrMailServer.create({
            'name': values.pop('name', 'smtp'), 'smtp_host': 'localhost',
            **values})


@pytest.fixture
def external_allowed():
    SystemParameter.set_param(EXTERNAL_SERVER_PARAM, 'True')


def test_the_user_reads_its_personal_server():
    user = _user('ana@kaupamex.mx', email='ana@kaupamex.mx')
    server = _server(name='ana', from_filter='ana@kaupamex.mx',
                     smtp_user='ana@kaupamex.mx', owner_user_id=user)
    assert user.outgoing_mail_server_id == server
    assert user.outgoing_mail_server_type == 'default'


def test_without_personal_server_the_reading_is_empty():
    user = _user('beto@kaupamex.mx', email='beto@kaupamex.mx')
    assert not user.outgoing_mail_server_id
    assert user.outgoing_mail_server_type == 'default'


def test_the_external_server_flag_follows_the_parameter():
    user = _user('carla@kaupamex.mx')
    SystemParameter.objects.filter(key=EXTERNAL_SERVER_PARAM).delete()
    assert not user.has_external_mail_server
    SystemParameter.set_param(EXTERNAL_SERVER_PARAM, 'True')
    # el valor no almacenado queda en la caché de la transacción por
    # registro, como en la fuente: lo lee un usuario aún no leído
    assert _user('carla2@kaupamex.mx').has_external_mail_server


def test_the_three_fields_are_self_readable():
    readable = ResUsers().SELF_READABLE_FIELDS
    for name in ('has_external_mail_server', 'outgoing_mail_server_id',
                 'outgoing_mail_server_type'):
        assert name in readable


def test_setup_is_refused_without_the_parameter():
    SystemParameter.objects.filter(key=EXTERNAL_SERVER_PARAM).delete()
    user = _user('dora@kaupamex.mx', email='dora@kaupamex.mx')
    with user_scope(user.pk), pytest.raises(UserError):
        ResUsers.action_setup_outgoing_mail_server('gmail')


def test_setup_is_refused_to_a_non_internal_user(external_allowed):
    user = _user('eva@kaupamex.mx', email='eva@kaupamex.mx',
                 internal=False)
    with user_scope(user.pk), pytest.raises(UserError):
        ResUsers.action_setup_outgoing_mail_server('gmail')


def test_default_removes_the_personal_server(external_allowed):
    user = _user('fer@kaupamex.mx', email='fer@kaupamex.mx')
    _server(name='fer', from_filter='fer@kaupamex.mx', owner_user_id=user)
    with user_scope(user.pk):
        action = ResUsers.action_setup_outgoing_mail_server('default')
    assert action['tag'] == 'display_notification'
    assert not IrMailServer.objects.filter(owner_user_id=user).exists()


def test_an_alias_domain_address_is_refused(external_allowed):
    MailAliasDomain.objects.create(name='kaupamex.mx', default_from='gabo')
    user = _user('gabo@kaupamex.mx', email='gabo@kaupamex.mx')
    with user_scope(user.pk), pytest.raises(UserError):
        ResUsers.action_setup_outgoing_mail_server('gmail')


def test_setup_creates_an_archived_server_for_the_provider(external_allowed):
    user = _user('hugo@otra.mx', email='Hugo@Otra.mx')
    with user_scope(user.pk), pytest.raises(NotImplementedError):
        ResUsers.action_setup_outgoing_mail_server('gmail')
    server = IrMailServer.objects.get(owner_user_id=user)
    assert server.active is False
    assert server.from_filter == 'hugo@otra.mx'
    assert server.smtp_user == 'hugo@otra.mx'
    assert (server.smtp_port, server.smtp_encryption) == (587, 'starttls')


def test_testing_without_a_server_is_refused(external_allowed):
    user = _user('ines@kaupamex.mx', email='ines@kaupamex.mx')
    with user_scope(user.pk), pytest.raises(UserError):
        ResUsers.action_test_outgoing_mail_server()


def test_the_vacuum_drops_archived_and_unused_personal_servers():
    user = _user('juan@kaupamex.mx', email='juan@kaupamex.mx')
    stale = _server(name='viejo', from_filter='viejo@kaupamex.mx',
                    owner_user_id=user)
    public = _server(name='publico')
    ResUsers._gc_personal_mail_servers()
    assert not IrMailServer.objects.filter(pk=stale.id).exists()
    assert IrMailServer.objects.filter(pk=public.id).exists()


def test_a_personal_server_is_forced_only_by_its_owner():
    owner = _user('kim@kaupamex.mx', email='kim@kaupamex.mx')
    server = _server(name='kim', from_filter='kim@kaupamex.mx',
                     smtp_user='kim@kaupamex.mx', owner_user_id=owner)
    model = Environment(uid=SUPERUSER_ID)['ir.mail_server']
    with sudo():
        model._check_forced_mail_server(server, False, 'kim@kaupamex.mx')
        with pytest.raises(UserError, match='belongs to a user'):
            model._check_forced_mail_server(server, False,
                                            'otro@kaupamex.mx')
