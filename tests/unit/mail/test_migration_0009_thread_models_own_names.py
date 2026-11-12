"""``mail/0009``: mensajes, seguidores y actividades guardados con el label
de los nueve modelos que declararon su ``_name`` pasan a la nueva clave.

designs/analytic-account-header.md.
"""
import importlib

import pytest
from django.apps import apps
from django.db import connection

migration = importlib.import_module(
    'addons.mail.migrations.0009_thread_models_own_names')

pytestmark = pytest.mark.django_db


def _message(model):
    return apps.get_model('mail', 'MailMessage').objects.create(
        model=model, res_id=1, body='x')


def _run(direction):
    with connection.schema_editor(atomic=False) as editor:
        direction(apps, editor)


def test_a_label_key_moves_to_the_declared_name():
    old = _message('helpdesk.SupportTicket')
    _run(migration.forwards)
    old.refresh_from_db()
    assert old.model == 'support.ticket'


def test_other_models_keep_their_key():
    other = _message('crm.lead')
    _run(migration.forwards)
    other.refresh_from_db()
    assert other.model == 'crm.lead'


def test_backwards_restores_the_label():
    row = _message('fleet.FleetVehicle')
    _run(migration.forwards)
    _run(migration.backwards)
    row.refresh_from_db()
    assert row.model == 'fleet.FleetVehicle'


def test_every_renamed_label_is_a_live_model_with_that_name():
    for label, name in migration.RENAMED.items():
        assert apps.get_model(label)._name == name
