"""Los métodos privados de ``ir.mail_server`` con sus nombres de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``:
``_active_usages_compute`` (``:266-273``), ``_get_max_email_size``
(``:275-278``) y ``_get_test_email_from`` (``:280-295``), y el guardián de
archivado que lee ``_active_usages_compute`` (``write``, ``:231-264``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 1.
"""
from unittest import mock

import pytest
from django.core.exceptions import ValidationError

from addons.base.models.ir_mail_server import IrMailServer


def test_no_module_declares_usages_by_default():
    assert IrMailServer(name='smtp')._active_usages_compute() == {}


def test_a_server_in_use_cannot_be_archived():
    server = IrMailServer(pk=7, name='smtp')
    with mock.patch.object(IrMailServer, '_active_usages_compute',
                           return_value={7: ['Newsletter']}):
        with pytest.raises(ValidationError, match='Newsletter'):
            server.check_can_archive()


def test_a_server_without_usages_can_be_archived():
    IrMailServer(pk=7, name='smtp').check_can_archive()


def test_several_servers_in_use_are_named_in_order():
    first, second = IrMailServer(pk=1, name='b'), IrMailServer(pk=2, name='a')
    with mock.patch.object(IrMailServer, '_active_usages_compute',
                           return_value={1: ['x'], 2: ['y']}):
        with pytest.raises(ValidationError, match=r'\(a, b\)'):
            IrMailServer.check_can_archive_many([first, second])


def test_the_server_size_wins_over_the_default():
    assert IrMailServer(max_email_size=25)._get_max_email_size() == 25.0


@pytest.mark.django_db
def test_without_server_size_the_parameter_applies():
    assert IrMailServer(max_email_size=0)._get_max_email_size() > 0


def test_the_test_sender_is_the_first_complete_email_of_the_filter():
    server = IrMailServer(from_filter='kaupamex.mx, ana@kaupamex.mx')
    assert server._get_test_email_from() == 'ana@kaupamex.mx'


def test_a_domain_only_filter_gives_noreply():
    server = IrMailServer(from_filter='kaupamex.mx')
    assert server._get_test_email_from() == 'noreply@kaupamex.mx'


def test_without_filter_or_fallback_the_test_sender_is_refused():
    with pytest.raises(ValidationError):
        IrMailServer(from_filter='')._get_test_email_from()
