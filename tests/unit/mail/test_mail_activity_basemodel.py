"""``mail.activity`` y ``mail.activity.type`` sobre ``BaseModel``, con su ACL.

≙ ``odoo19c: addons/mail/models/mail_activity.py`` y
``odoo19c: addons/mail/models/mail_activity_type.py``, y las filas de
``odoo19c: addons/mail/security/ir.model.access.csv`` cuyo modelo tiene fila
en ``ir.model``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-mail-activity.md``.

*Métrica:* el tipo de cada modelo y las filas cargadas con el identificador
externo del módulo.
*Ciega a:* las 65 filas de modelos sin puerto o sin cabecera, que el
manifiesto declara, y a ``mail.activity.mixin``, que espera a sus herederos.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelAccess, IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name', ['mail.activity', 'mail.activity.type'])
def test_each_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_acl_rows_that_resolve_load():
    xmlids = set(IrModelData.objects.filter(
        module='mail', model='base.IrModelAccess',
    ).values_list('name', flat=True))
    assert {
        'access_mail_activity_user',
        'access_mail_activity_type_user',
        'access_mail_activity_type_system',
        'ir_actions_report_access_user',
    } <= xmlids
    row = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='mail', name='access_mail_activity_type_user').res_id)
    assert (row.perm_read, row.perm_write, row.perm_create,
            row.perm_unlink) == (True, False, False, False)


def test_an_internal_user_reads_but_does_not_write_activity_types():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='activity-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        types = Environment(uid=user.pk)['mail.activity.type']
        types.check_access('read')
        with pytest.raises(AccessError):
            types.check_access('write')
