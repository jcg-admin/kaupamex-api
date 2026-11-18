"""Una unidad de trabajo por orden de gestión.

≙ ``with registry.cursor() as cr:`` alrededor de cada orden de ``odoo-bin``
que toca datos (``odoo19c: odoo/cli/shell.py:138``,
``odoo19c: odoo/cli/populate.py:59``): COMMIT si la orden termina bien,
reversión si lanza. Diseño en ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
management-command-unit-of-work.md``.
"""
import importlib
import pathlib

import pytest
from django.apps import apps
from django.core.management.base import BaseCommand

from addons.base.management.unit_of_work import UnitOfWorkCommand
from orm import registry as orm_registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')
ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Las órdenes que no son una unidad, con su razón (diseño, tabla).
OUTSIDE = {
    'server': 'sirve peticiones; cada una abre la suya',
    'cron': 'cada trabajo corre en su propio cursor',
    'company_create': 'CREATE DATABASE no admite transacción',
    'company_migrate_all': 'migra bases enteras, una transacción por paso',
}


@pytest.fixture
def calls(monkeypatch):
    seen = []
    for name in ('signal_changes', 'reset_changes', 'check_signaling'):
        def record(self, *args, _name=name, **kwargs):
            seen.append(_name)
            return self if _name == 'check_signaling' else None
        monkeypatch.setattr(orm_registry.Registry, name, record)
    return seen


class Boom(Exception):
    pass


def _command(body):
    class Probe(UnitOfWorkCommand):
        def handle(self, *args, **options):
            body()
    return Probe()


def _run(command):
    command.execute(no_color=True, force_color=False, skip_checks=True,
                    database='default', verbosity=0)


def _create(name):
    with Environment('default', SUPERUSER_ID, {}) as env:
        return env['test_orm.shared.compute'].create({'name': name}).id


def test_a_command_that_ends_well_commits_and_signals(calls):
    created = []
    _run(_command(lambda: created.append(_create('2->3'))))
    assert SharedCompute.objects.filter(pk=created[0]).exists()
    assert calls == ['check_signaling', 'signal_changes']


def test_a_command_that_raises_rolls_back_and_resets(calls):
    created = []

    def body():
        created.append(_create('4->5'))
        raise Boom('deshacer')

    with pytest.raises(Boom):
        _run(_command(body))
    assert not SharedCompute.objects.filter(pk=created[0]).exists()
    assert calls == ['check_signaling', 'reset_changes']


def test_pending_orm_work_reaches_the_row_before_commit(calls):
    created = []

    def body():
        with Environment('default', SUPERUSER_ID, {}) as env:
            record = env['test_orm.shared.compute'].create({'name': '2->5'})
            record.name = '3->6'          # recómputo pendiente
            created.append(record.id)

    _run(_command(body))
    row = SharedCompute.objects.values('start', 'end').get(pk=created[0])
    assert row == {'start': 3, 'end': 6}


def _own_commands():
    for path in sorted(ROOT.glob('*/addons/*/management/commands/*.py')) + \
            sorted(ROOT.glob('addons/*/management/commands/*.py')):
        if path.stem == '__init__':
            continue
        app = path.parents[2].name
        yield path.stem, importlib.import_module(
            f'addons.{app}.management.commands.{path.stem}').Command


def test_every_own_command_runs_in_a_unit_of_work():
    outside = sorted(name for name, command in _own_commands()
                     if not issubclass(command, UnitOfWorkCommand)
                     and name not in OUTSIDE)
    assert outside == []


def test_the_commands_left_outside_are_plain_commands():
    commands = dict(_own_commands())
    assert set(OUTSIDE) <= set(commands)
    assert not any(issubclass(commands[name], UnitOfWorkCommand)
                   for name in OUTSIDE)
    assert all(issubclass(commands[name], BaseCommand) for name in OUTSIDE)
