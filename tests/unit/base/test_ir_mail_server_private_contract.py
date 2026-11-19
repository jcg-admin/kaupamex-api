"""Los métodos privados de ``ir.mail_server`` con sus nombres de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py``:
``_active_usages_compute`` (``:266-273``), ``_get_max_email_size``
(``:275-278``) y ``_get_test_email_from`` (``:280-295``).
El guardián de archivado se mide en ``test_ir_mail_server_basemodel.py``,
sobre el ``write`` que lo porta. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 1.
"""
import pytest

from addons.base.models.ir_mail_server import IrMailServer


def test_no_module_declares_usages_by_default():
    assert IrMailServer(name='smtp')._active_usages_compute() == {}


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
