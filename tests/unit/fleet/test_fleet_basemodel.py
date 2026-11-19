"""``fleet`` sobre ``BaseModel``, con sus cabeceras y su seguridad.

≙ los once modelos de ``odoo19c: addons/fleet/models/`` y los dos archivos de
``odoo19c: addons/fleet/security/``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-fleet.md``.

*Métrica:* el tipo y la cabecera de cada modelo, y las filas cargadas con el
identificador externo del módulo.
*Ciega a:* los registros de los modelos sin puerto (informes y el asistente
de correo), que el manifiesto declara.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


@pytest.fixture
def superuser_env():
    """Sin el entorno de superusuario del ``conftest``: estas pruebas miden
    la ACL, y la última abre su propio usuario interno."""
    yield None


HEADERS = {
    'fleet.service.type': ('Fleet Service Type', 'name'),
    'fleet.vehicle.assignation.log': (
        'Drivers history on a vehicle', 'create_date desc, date_start desc'),
    'fleet.vehicle.model.brand': ('Brand of the vehicle', 'name asc'),
    'fleet.vehicle.model.category': (
        'Category of the model', 'sequence asc, id asc'),
    'fleet.vehicle.odometer': ('Odometer log for a vehicle', 'date desc'),
    'fleet.vehicle.state': ('Vehicle Status', 'sequence asc'),
    'fleet.vehicle.tag': ('Vehicle Tag', None),
}
NAMED = ('fleet.vehicle', 'fleet.vehicle.model',
         'fleet.vehicle.log.contract', 'fleet.vehicle.log.services')


@pytest.mark.parametrize('name', sorted(HEADERS) + list(NAMED))
def test_each_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


@pytest.mark.parametrize('name', sorted(HEADERS))
def test_each_header_is_the_reference(name):
    model = MODELS_BY_NAME[name]
    description, order = HEADERS[name]
    assert model.__dict__['_description'] == description
    if order is not None:
        assert model.__dict__['_order'] == order


def test_the_groups_and_rules_load():
    names = set(IrModelData.objects.filter(
        module='fleet').values_list('name', flat=True))
    assert {'fleet_group_user', 'fleet_group_manager',
            'ir_rule_fleet_vehicle', 'ir_rule_fleet_odometer',
            'fleet_rule_vehicle_visibility_manager'} <= names


def test_the_acl_rows_that_resolve_load():
    """Las 24 de la fuente menos las tres de modelos sin puerto."""
    assert IrModelData.objects.filter(
        module='fleet', model='base.IrModelAccess').count() == 21


def test_an_internal_user_without_fleet_rights_cannot_read():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='fleet-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        vehicles = Environment(uid=user.pk)['fleet.vehicle']
        with pytest.raises(AccessError):
            vehicles.check_access('read')
