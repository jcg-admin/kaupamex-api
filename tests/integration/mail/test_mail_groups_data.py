"""Los grupos de ``mail``, cargados por el manifiesto en la instalación.

≙ ``odoo19c: addons/mail/data/mail_groups.xml`` y la implicación de
``group_sale_manager`` (``odoo19c: addons/sales_team/security/
sales_team_security.xml:30``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/mail-groups-data.md``.
"""
from types import SimpleNamespace

import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelData
from modules.loading import load_data
from modules.module import get_manifest
from orm.environments import sudo
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def _install(module):
    """``load_data`` en ``mode='init'``, como en la instalación.

    Los registros son ``noupdate``: en modo de actualización la base
    reutilizada no los reescribiría.
    """
    package = SimpleNamespace(name=module, manifest=get_manifest(module))
    load_data({}, 'init', 'data', package, using=DEFAULT_DB_ALIAS)


def _record(model, module, name):
    res_id = IrModelData.objects.get(module=module, name=name).res_id
    return MODELS_BY_NAME[model].objects.get(pk=res_id)


#: Los registros de ``mail_groups.xml``, en orden de borrado: los grupos
#: antes que el privilegio al que apuntan.
MAIL_RECORDS = (
    ('res.groups', 'group_mail_canned_response_admin'),
    ('res.groups', 'group_mail_template_editor'),
    ('res.groups', 'group_mail_notification_type_inbox'),
    ('res.groups.privilege', 'res_groups_privilege_canned_response'),
)


@pytest.fixture
def installed_mail():
    """Los grupos de ``mail`` como los deja una instalación nueva.

    El arranque de la sesión de pruebas ya cargó los datos del manifiesto en
    la base reutilizada, fuera de la transacción de cada prueba. Se retiran
    primero, para que sólo los cree el ``load_data`` de la prueba. Borrar un
    grupo quita también sus implicaciones.
    """
    with sudo():
        for model, name in MAIL_RECORDS:
            rows = IrModelData.objects.filter(module='mail', name=name)
            MODELS_BY_NAME[model].objects.filter(
                pk__in=list(rows.values_list('res_id', flat=True))).delete()
            rows.delete()
    _install('mail')


def test_the_canned_response_group_has_its_privilege(installed_mail):
    privilege = _record('res.groups.privilege', 'mail',
                        'res_groups_privilege_canned_response')
    assert privilege.name == 'Canned Responses'
    assert privilege.sequence == 100
    assert privilege.category_id == IrModelData.objects.get(
        module='base', name='module_category_marketing').res_id
    group = _record('res.groups', 'mail', 'group_mail_canned_response_admin')
    assert group.name == 'Canned Response Administrator'
    assert group.privilege_id == privilege.pk


def test_the_other_mail_groups_exist(installed_mail):
    assert _record('res.groups', 'mail',
                   'group_mail_template_editor').name == 'Mail Template Editor'
    assert _record('res.groups', 'mail',
                   'group_mail_notification_type_inbox').name == (
        'Receive notifications in Odoo')


def test_the_system_group_implies_both_mail_groups(installed_mail):
    system = _record('res.groups', 'base', 'group_system')
    implied = set(system.implied_ids.all())
    assert _record('res.groups', 'mail', 'group_mail_template_editor') in (
        implied)
    assert _record('res.groups', 'mail',
                   'group_mail_canned_response_admin') in implied


def test_the_sales_manager_implies_the_canned_response_admin(installed_mail):
    _install('sales_team')
    manager = _record('res.groups', 'sales_team', 'group_sale_manager')
    assert _record('res.groups', 'mail',
                   'group_mail_canned_response_admin') in (
        manager.implied_ids.all())
