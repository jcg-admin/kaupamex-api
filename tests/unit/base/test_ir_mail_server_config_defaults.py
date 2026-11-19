"""Los valores por defecto de ``ir.mail_server`` leen ``tools.config``.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py:645-677``: el rebote
y el remitente devuelven ``tools.config.get('email_from')``, y el filtro cae
a ``tools.config.get('from_filter')`` cuando falta el parámetro de sistema.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
base-ir-mail-server-complete.md``, paso 3b.
"""
import pytest
from django.test import override_settings

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_mail_server import (
    DEFAULT_FROM_FILTER_PARAM,
    IrMailServer,
)

pytestmark = pytest.mark.django_db


@override_settings(DEFAULT_FROM_EMAIL='')
def test_without_a_sender_the_bounce_is_the_empty_config_value():
    assert IrMailServer._get_default_bounce_address() == ''
    assert IrMailServer._get_default_from_address() == ''


@override_settings(EMAIL_FROM_FILTER='kaupamex.mx')
def test_the_filter_falls_back_to_the_config_value():
    SystemParameter.objects.filter(key=DEFAULT_FROM_FILTER_PARAM).delete()
    assert IrMailServer._get_default_from_filter() == 'kaupamex.mx'


@override_settings(EMAIL_FROM_FILTER='kaupamex.mx')
def test_the_system_parameter_wins_over_the_config_value():
    SystemParameter.set_param(DEFAULT_FROM_FILTER_PARAM, 'otra.mx')
    assert IrMailServer._get_default_from_filter() == 'otra.mx'
