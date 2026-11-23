"""``sembrar_cron`` siembra un cron inactivo y con identificador externo.

≙ el ``<record model="ir.cron">`` de la fuente, que declara ``active`` y un
``id`` (p. ej. ``odoo19c: addons/account_edi/data/cron.xml:2-10``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
account-edi-network-cron.md``.

*Métrica:* el ``active`` del cron sembrado y su fila de ``ir.model.data``.
*Ciega a:* el runner, que tiene sus propias pruebas.
"""
import pytest
from django.apps import apps

from addons.base.data.cron import sembrar_cron, sembrar_cron_vivo
from addons.base.models import IrModelData
from orm.environments import env

pytestmark = pytest.mark.django_db

SPEC = {
    'name': 'Control inactivo',
    'model_name': 'ir.cron',
    'method_name': 'method_direct_trigger',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 5,
    'active': False,
    'xml_id': 'base.ctl_inactive_seed_cron',
}


@pytest.mark.parametrize('seed', [
    lambda spec: sembrar_cron(apps, 'default', spec),
    lambda spec: sembrar_cron_vivo(spec),
], ids=['migration', 'live'])
def test_the_spec_declares_active_and_external_id(seed):
    cron, created = seed(SPEC)
    assert created
    assert cron.active is False
    assert env().ref('base.ctl_inactive_seed_cron').pk == cron.pk
    again, created_again = seed(SPEC)
    assert again.pk == cron.pk and not created_again
    assert IrModelData.objects.filter(
        module='base', name='ctl_inactive_seed_cron').count() == 1


def test_a_spec_without_the_keys_seeds_an_active_cron_without_id():
    spec = {key: value for key, value in SPEC.items()
            if key not in ('active', 'xml_id')}
    spec['method_name'] = '_callback'
    cron, _created = sembrar_cron(apps, 'default', spec)
    assert cron.active is True
    assert not IrModelData.objects.filter(
        model='ir.cron', res_id=cron.pk).exists()
