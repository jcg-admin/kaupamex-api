"""El registro de intención de ci-multidb y la recuperación de sus restos.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
multidb-run-intent-ledger.md``. Un reclamo del contenedor mata la ejecución
antes de ``drop_created``; sin un registro previo de qué bases iba a crear,
su procedencia no se puede demostrar y la limpieza no es admisible.
"""
import importlib
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]
                       / 'scripts'))
runner = importlib.import_module('run_multidb_isolation')

ROLE = 'orm_x2hokp'


class _Catalog:
    """Doble de ``pg_database``/``pg_stat_activity`` que anota los DROP."""

    def __init__(self, databases):
        self.databases = dict(databases)  # nombre -> (dueño, sesiones)
        self.dropped = []

    def __call__(self, env, dbname='postgres'):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        name = params[0] if params else None
        if sql.startswith('DROP DATABASE'):
            target = sql.split('"')[1]
            self.dropped.append(target)
            del self.databases[target]
            return _Rows([])
        if 'pg_stat_activity' in sql:
            return _Rows([(self.databases[name][1],)])
        if name in self.databases:
            return _Rows([(self.databases[name][0],)])
        return _Rows([])


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


def _intent(run_dir, databases, role=ROLE):
    run_dir.mkdir()
    runner.write_intent(run_dir, {'databases': databases, 'role': role})
    return run_dir


def test_the_intent_names_the_three_databases(tmp_path):
    intent = runner.planned_databases('orm_bootstrap_ab', 41)
    assert intent == ['orm_bootstrap_ab', 'company_41_db', 'company_42_db']
    runner.write_intent(tmp_path, {'databases': intent, 'role': ROLE})
    saved = json.loads((tmp_path / 'intent.json').read_text())
    assert saved['databases'] == intent


def test_reclaim_drops_only_what_an_interrupted_run_declared(tmp_path):
    run = _intent(tmp_path / 'run', ['orm_bootstrap_ab', 'company_41_db',
                                     'company_42_db'])
    catalog = _Catalog({'orm_bootstrap_ab': (ROLE, 0),
                        'company_41_db': (ROLE, 0),
                        'company_7_db': (ROLE, 0)})
    result = runner.reclaim({'DB_QA_USER': ROLE}, [run], connect=catalog)
    assert catalog.dropped == ['orm_bootstrap_ab', 'company_41_db']
    assert 'company_7_db' in catalog.databases
    assert result[str(run)]['dropped'] == catalog.dropped
    assert (run / 'reclaimed.json').exists()


def test_reclaim_refuses_another_owner_or_open_sessions(tmp_path):
    run = _intent(tmp_path / 'run', ['company_41_db', 'company_42_db'])
    catalog = _Catalog({'company_41_db': ('someone_else', 0),
                        'company_42_db': (ROLE, 2)})
    result = runner.reclaim({'DB_QA_USER': ROLE}, [run], connect=catalog)
    assert catalog.dropped == []
    assert result[str(run)]['refused'] == {'company_41_db': 'owner',
                                           'company_42_db': 'sessions'}


def test_a_finished_run_is_not_reclaimed(tmp_path):
    run = _intent(tmp_path / 'run', ['orm_bootstrap_ab'])
    (run / 'record.json').write_text('{}')
    catalog = _Catalog({'orm_bootstrap_ab': (ROLE, 0)})
    result = runner.reclaim({'DB_QA_USER': ROLE}, [run], connect=catalog)
    assert catalog.dropped == [] and result[str(run)] == 'finished'


def test_without_an_intent_nothing_is_reclaimed(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    catalog = _Catalog({'orm_bootstrap_ab': (ROLE, 0)})
    result = runner.reclaim({'DB_QA_USER': ROLE}, [run], connect=catalog)
    assert catalog.dropped == [] and result[str(run)] == 'no-intent'
