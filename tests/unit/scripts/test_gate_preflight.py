"""El preflight del gate detecta una base que no sirve antes de lanzarla.

``scripts/gate_preflight.py`` (intervención 4.3.1 §3.5). Los positivos son
los dos defectos reales del 2026-11-17, reproducidos dentro de la
transacción de la prueba, que se revierte: el socio del usuario ``id=1`` sin
``commercial_partner_id`` y una migración que la base no tiene.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest
from django.db import connection

from addons.base.models import IrModelData, ResUsers

pytestmark = pytest.mark.django_db

_PATH = pathlib.Path(__file__).resolve().parents[3] / 'scripts' / (
    'gate_preflight.py')
_spec = importlib.util.spec_from_file_location('gate_preflight', _PATH)
gate_preflight = importlib.util.module_from_spec(_spec)
sys.modules['gate_preflight'] = gate_preflight
_spec.loader.exec_module(gate_preflight)


def test_a_sound_database_has_no_reference_problems():
    """Control: la base de la suite, tal como está, sirve."""
    with connection.cursor() as cursor:
        assert gate_preflight.reference_problems(cursor) == []


def test_a_missing_commercial_partner_is_reported():
    """El defecto que hizo fallar la carga de ``account_security.xml``."""
    partner = ResUsers.objects.get(pk=1).partner
    type(partner).objects.filter(pk=partner.pk).update(
        commercial_partner_id=None)
    with connection.cursor() as cursor:
        assert gate_preflight.reference_problems(cursor) == [
            'el socio del usuario id=1 no tiene commercial_partner_id '
            'calculado']


@pytest.mark.parametrize('name, problem', [
    ('user_root', 'falta el XML-ID base.user_root'),
    ('public_user', 'falta el XML-ID base.public_user'),
    ('paperformat_euro', 'falta el XML-ID base.paperformat_euro'),
])
def test_a_half_reseeded_database_is_reported(name, problem):
    """El defecto real del 2026-11-17: una resiembra cortada dejó la fila
    del usuario 1 sin su XML-ID y el preflight dio la base por buena."""
    IrModelData.objects.filter(module='base', name=name).delete()
    with connection.cursor() as cursor:
        assert gate_preflight.reference_problems(cursor) == [problem]


def test_no_migration_is_pending_on_the_suite_database():
    assert gate_preflight.pending_migrations(connection) == []


def test_an_unapplied_migration_is_reported():
    """Una migración borrada de ``django_migrations`` aparece pendiente."""
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM django_migrations WHERE app = 'purchase'"
            " AND name = '0022_line_date_planned'")
    assert ('purchase', '0022_line_date_planned') in (
        gate_preflight.pending_migrations(connection))


def test_each_xdist_worker_has_its_own_database():
    names = gate_preflight.database_names(4)
    assert len(names) == 4
    assert [name[-4:] for name in names] == ['_gw0', '_gw1', '_gw2', '_gw3']


def test_a_sibling_pytest_is_reported():
    """Positivo: un proceso vivo con «pytest» en su línea de comando que no
    es ancestro del preflight compite por las bases."""
    sibling = subprocess.Popen(
        ['bash', '-c', 'exec -a pytest-sibling sleep 30'])
    try:
        assert sibling.pid in gate_preflight.competing_pytest(os.getpid())
    finally:
        sibling.kill()
        sibling.wait()


def test_the_launching_shell_is_not_competition():
    """Control: el shell que lanza el preflight lleva «pytest» en su línea
    de comando y no se cuenta como competencia."""
    probe = (
        'import json, os, sys; sys.path.insert(0, sys.argv[1]); '
        'import gate_preflight as g; '
        'print(json.dumps([os.getppid(), g.competing_pytest(os.getpid())]))')
    script = (f'true pytest-launcher; {sys.executable} -c "{probe}" '
              f'{_PATH.parent}; true')
    result = subprocess.run(['bash', '-c', script], capture_output=True,
                            text=True, check=True)
    shell, competing = json.loads(result.stdout.strip().splitlines()[-1])
    assert shell not in competing


def test_preparation_migrates_only_a_database_with_pending_migrations(
        monkeypatch):
    """Una revisión con migraciones nuevas es el caso normal: la
    preparación las aplica; una base al día no recibe ``migrate``."""
    calls = []
    pending = {'orm_a': ['purchase.0023_x'], 'orm_b': []}
    monkeypatch.setattr(gate_preflight, 'pending_migrations',
                        lambda connection: pending[connection.alias[10:]])
    monkeypatch.setattr(gate_preflight, 'call_command',
                        lambda *args, **kwargs: calls.append(
                            kwargs['database']))
    assert gate_preflight.prepare_database('orm_a') == 1
    assert gate_preflight.prepare_database('orm_b') == 0
    assert calls == ['preflight_orm_a']
