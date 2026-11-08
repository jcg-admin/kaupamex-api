"""Qué viaja con ``copy``: el atributo ``copy`` de cada campo, como en la
referencia.

``odoo19c: odoo/orm/models.py:5436-5462``: ``copy_data`` recorre los campos
con ``field.copy``. Un ``One2many`` sólo se copia si declara ``copy=True``
—su defecto es ``False`` (``odoo19c: odoo/orm/fields_relational.py:869``)— y
un ``Many2many`` conserva los enlaces legibles con ``Command.set``.

Los cuatro casos son los de la referencia, con su línea:

- ``ir.actions.server.child_ids`` declara ``copy=True`` (``odoo19c:
  odoo/addons/base/models/ir_actions.py:649``);
- ``res.groups.model_access`` declara ``copy=True`` (``res_groups.py:24``);
- ``res.partner.child_ids`` no declara ``copy`` (``res_partner.py:217``):
  duplicar una empresa no duplica sus contactos;
- ``res.groups.implied_ids`` es un ``Many2many`` con el defecto
  (``res_groups.py:69``).

H-API-1161.
"""
import pytest

from addons.base.models.ir_actions import IrActionsServer
from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner
from orm.environments import sudo

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _as_superuser():
    """La copia pasa por ``create``, que aplica el acceso del modelo; la
    referencia mide como superusuario y aquí se salta igual."""
    with sudo():
        yield


def test_a_child_action_travels_with_the_copy(db):
    parent = IrActionsServer.objects.create(
        name='Padre 1161', type='ir.actions.server', state='multi')
    IrActionsServer.objects.create(
        name='Hija 1161', type='ir.actions.server', state='code',
        parent=parent)
    copy = parent.copy()
    assert [child.parent_id for child in copy.child_ids.all()] == [copy.pk]
    assert parent.child_ids.count() == 1


def test_the_access_rows_of_a_group_travel_with_the_copy(db):
    group = ResGroups.objects.create(name='Grupo 1161')
    model, _ = IrModel.objects.get_or_create(
        model='base.ResDeviceLog',
        defaults={'name': 'Registro de dispositivo'})
    IrModelAccess.objects.create(
        name='acl 1161', model_id=model, group_id=group, perm_read=True)
    copy = group.copy()
    rows = IrModelAccess.objects.filter(group_id=copy)
    assert [(row.name, row.model_id_id) for row in rows] == [
        ('acl 1161', model.pk)]


def test_the_contacts_of_a_company_stay_behind(db):
    company = ResPartner.objects.create(name='Empresa 1161', is_company=True)
    ResPartner.objects.create(name='Contacto 1161', parent=company)
    copy = company.copy()
    assert copy.children.count() == 0
    assert ResPartner.objects.filter(name='Contacto 1161').count() == 1


def test_the_implied_groups_are_kept_by_the_copy(db):
    implied = ResGroups.objects.create(name='Implicado 1161')
    group = ResGroups.objects.create(name='Implicante 1161')
    group.implied_ids.add(implied)
    copy = group.copy()
    assert list(copy.implied_ids.all()) == [implied]
