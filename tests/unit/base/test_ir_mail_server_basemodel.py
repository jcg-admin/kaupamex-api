"""``ir.mail_server`` sobre ``BaseModel``, con su ``write`` y sus métodos.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``: la cabecera
(``:142-145``), el guardián de archivado de ``write`` (``:231-264``),
``_check_forced_mail_server`` (``:546-548``), ``_get_default_bounce_address``
(``:646-654``) y ``_find_mail_server_allowed_domain`` (``:870-873``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 2.
"""
from unittest import mock

import pytest
from django.test import override_settings

from addons.base.models import IrModelAccess
from addons.base.models.ir_mail_server import IrMailServer
from exceptions import UserError
from orm.domains import Domain
from orm.environments import sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def test_the_server_is_a_base_model_with_the_source_header():
    assert issubclass(IrMailServer, BaseModel)
    assert IrMailServer._name == 'ir.mail_server'
    assert IrMailServer._description == 'Mail Server'
    assert IrMailServer._order == 'sequence, id'
    assert IrMailServer._allow_sudo_commands is False


def test_the_system_group_has_the_source_acl():
    row = IrModelAccess.objects.get(name='ir_mail_server')
    assert (row.perm_read, row.perm_write, row.perm_create,
            row.perm_unlink) == (True, True, True, True)


def _server(name):
    with sudo():
        return IrMailServer.create({'name': name, 'smtp_host': 'localhost'})


def test_a_server_in_use_cannot_be_archived():
    with sudo():
        server = _server('smtp-a')
        with mock.patch.object(IrMailServer, '_active_usages_compute',
                               return_value={server.id: ['Newsletter']}):
            with pytest.raises(UserError) as error:
                server.write({'active': False})
    message = str(error.value)
    assert message.startswith('You cannot archive this Outgoing Mail Server')
    assert '- Newsletter' in message
    assert 'Dedicated Outgoing Mail Server' not in message


def test_several_servers_in_use_are_listed_by_name():
    with sudo():
        first, second = _server('smtp-b'), _server('smtp-a')
        both = first | second
        with mock.patch.object(
                IrMailServer, '_active_usages_compute',
                return_value={first.id: ['x'], second.id: ['y']}):
            with pytest.raises(UserError) as error:
                both.write({'active': False})
    message = str(error.value)
    assert '(smtp-a, smtp-b)' in message
    assert 'smtp-a (Dedicated Outgoing Mail Server):' in message


def test_a_server_without_usages_is_archived():
    with sudo():
        server = _server('smtp-a')
        server.write({'active': False})
        assert not server.active


def test_an_archived_server_cannot_be_forced():
    with sudo():
        server = _server('smtp-a')
        server.write({'active': False})
        with pytest.raises(UserError, match='archived'):
            server._check_forced_mail_server(server, False, 'a@x.mx')
        server._check_forced_mail_server(server, True, 'a@x.mx')


@override_settings(DEFAULT_FROM_EMAIL='bounce@kaupamex.mx')
def test_the_default_bounce_is_the_configured_sender():
    assert IrMailServer._get_default_bounce_address() == 'bounce@kaupamex.mx'


def test_every_server_is_allowed_by_default():
    assert IrMailServer._find_mail_server_allowed_domain() == Domain.TRUE
