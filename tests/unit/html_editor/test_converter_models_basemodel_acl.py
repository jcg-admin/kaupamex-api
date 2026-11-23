"""Los modelos de conversión de ``html_editor`` sobre ``BaseModel``.

≙ ``odoo19c: addons/html_editor/models/test_models.py:6-8`` y ``:32-34``
(los dos son ``BaseModel``) y
``odoo19c: addons/html_editor/security/ir.model.access.csv`` (una fila por
modelo, todo para ``base.group_system``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-html-editor.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from addons.html_editor.models.test_models import (
    Html_EditorConverterTest,
    Html_EditorConverterTestSub,
)
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _user(login, *groups):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for name in groups:
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module='base', name=name).res_id))
    return user


@pytest.mark.parametrize('model', [
    Html_EditorConverterTest, Html_EditorConverterTestSub])
def test_both_models_are_base_models(model):
    assert issubclass(model, BaseModel)


def test_the_acl_is_the_reference_csv_with_its_external_ids():
    loaded = IrModelData.objects.filter(module='html_editor',
                                        model='ir.model.access')
    names = sorted(loaded.values_list('name', flat=True))
    assert names == ['access_html_editor_converter_test',
                     'access_html_editor_converter_test_sub']
    for name in names:
        row = IrModelAccess.objects.get(pk=loaded.get(name=name).res_id)
        assert (row.perm_read, row.perm_write, row.perm_create,
                row.perm_unlink) == (True, True, True, True)


def test_only_a_system_user_reads_the_converter_test():
    internal = _user('converter-acl-internal', 'group_user')
    with user_scope(internal.pk), pytest.raises(AccessError):
        Environment(uid=internal.pk)['html_editor.converter.test'].search([])
    admin = _user('converter-acl-system', 'group_user', 'group_system')
    with user_scope(admin.pk):
        found = Environment(uid=admin.pk)[
            'html_editor.converter.test'].search([])
    assert not found
