"""Cada cron sembrado se identifica por su ``xml_id``, como en la fuente.

La fuente nombra cada cron por el ``id`` de su ``<record model="ir.cron">`` y
lo pide con ``env.ref`` (p. ej. ``odoo19c: addons/base_automation/models/
base_automation.py:647-660``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/cron-xml-id-natural-key.md``.

*Métrica:* el cron al que resuelve ``env().ref`` y las filas de acción y cron
que deja una segunda siembra.
*Ciega a:* lo que cada cron ejecuta, que miden las pruebas de su addon.
"""
from unittest import mock

import pytest
from django.apps import apps

from addons.auto_backup.data import CRON_BACKUP
from addons.auto_backup.models.db_backup import DbBackup
from addons.base.data import CRON_AUTOVACUUM
from addons.base.data.cron import sembrar_cron, sembrar_cron_vivo
from addons.base.models import IrActionsServer, IrCron, IrModelData
from addons.base_automation.data import CRON_BASE_AUTOMATION_CHECK
from addons.base_automation.models.base_automation import BaseAutomation
from addons.helpdesk.data import CRON_AUTO_CLOSE_TICKETS
from addons.loyalty.data import CRON_EXPIRE_VOUCHERS
from addons.mail.data import CRON_EMAIL_QUEUE
from addons.website_sale.models.website import CRON_SEND_ABANDONED_CART_EMAIL
from addons.account_edi.data import CRON_EDI_NETWORK
from orm.environments import env

pytestmark = pytest.mark.django_db

SEEDED_SPECS = (
    CRON_AUTOVACUUM, CRON_BACKUP, CRON_BASE_AUTOMATION_CHECK,
    CRON_AUTO_CLOSE_TICKETS, CRON_EXPIRE_VOUCHERS, CRON_EMAIL_QUEUE,
    CRON_SEND_ABANDONED_CART_EMAIL, CRON_EDI_NETWORK,
)

SPEC = {
    'name': 'Control de identidad',
    'model_name': 'ir.cron',
    'method_name': 'method_direct_trigger',
    'interval_number': 1,
    'interval_type': 'days',
    'priority': 5,
    'xml_id': 'base.ctl_identity_seed_cron',
}

SEEDERS = [
    pytest.param(lambda spec: sembrar_cron(apps, 'default', spec),
                 id='migration'),
    pytest.param(sembrar_cron_vivo, id='live'),
]


@pytest.mark.parametrize('spec', SEEDED_SPECS,
                         ids=lambda spec: spec['xml_id'])
def test_every_seeded_cron_has_its_xml_id(spec):
    cron = env().ref(spec['xml_id'])
    assert isinstance(cron, IrCron)
    assert cron.ir_actions_server.model_name == spec['model_name']


@pytest.mark.parametrize('seed', SEEDERS)
def test_seed_links_xml_id_to_legacy_row(seed):
    legacy = {key: value for key, value in SPEC.items() if key != 'xml_id'}
    cron, _created = seed(legacy)
    assert not IrModelData.objects.filter(
        module='base', name='ctl_identity_seed_cron').exists()
    again, created = seed(SPEC)
    assert again.pk == cron.pk and not created
    assert env().ref('base.ctl_identity_seed_cron').pk == cron.pk


@pytest.mark.parametrize('seed', SEEDERS)
def test_seed_finds_cron_by_xml_id(seed):
    cron, _created = seed(SPEC)
    action = cron.ir_actions_server
    IrActionsServer.objects.filter(pk=action.pk).update(
        method_name='_callback')
    actions_before = IrActionsServer.objects.count()
    again, created = seed(SPEC)
    assert again.pk == cron.pk and not created
    assert IrActionsServer.objects.count() == actions_before


def test_base_automation_cron_is_seeded_inactive():
    """Sembrado sobre una base sin él nace inactivo. Una base que ya lo
    tenía conserva su estado, como ``noupdate`` en la fuente."""
    cron = env().ref('base_automation.ir_cron_data_base_automation_check')
    action = cron.ir_actions_server
    IrModelData.objects.filter(
        module='base_automation',
        name='ir_cron_data_base_automation_check').delete()
    cron.delete()
    action.delete()
    seeded, created = sembrar_cron(apps, 'default', CRON_BASE_AUTOMATION_CHECK)
    assert created and seeded.active is False
    assert env().ref(
        'base_automation.ir_cron_data_base_automation_check').pk == seeded.pk


def test_base_automation_finds_its_cron_by_xml_id():
    cron = env().ref('base_automation.ir_cron_data_base_automation_check')
    IrActionsServer.objects.filter(pk=cron.ir_actions_server_id).update(
        method_name='')
    assert BaseAutomation().action_open_scheduled_action().pk == cron.pk


def test_backup_reads_its_cron_by_xml_id():
    cron = env().ref('auto_backup.backup_scheduler')
    IrActionsServer.objects.filter(pk=cron.ir_actions_server_id).update(
        method_name='')
    with mock.patch.object(IrCron, 'method_direct_trigger',
                           autospec=True) as trigger:
        assert DbBackup.action_run_cron() is not False
    assert trigger.call_args.args[0].pk == cron.pk
