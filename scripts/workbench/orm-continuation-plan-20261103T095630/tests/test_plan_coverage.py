"""Contrato de ``probes/plan_coverage.py``: frontera vacía no es aceptación.

La frontera de ``continuation_frontier.runnable_items`` sólo ve ``plan.jsonl``.
Estos casos fijan las tres situaciones que la iniciativa debe distinguir —A
criterios satisfechos, B trabajo pendiente y admisible, C trabajo pendiente sin
nada admisible— y que ninguna termine en ACCEPTED por un conteo en cero.
"""
import importlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'probes'))
sys.path.insert(0, '/home/user/thyrox/src')

classify = importlib.import_module('plan_coverage').classify
append_log = importlib.import_module('session.task_continuation').append_log
CONTROLLER = '/home/user/thyrox/bin/task_continuation'
plan_items_from_rows = importlib.import_module(
    'session.task_continuation').plan_items_from_rows


def plan(*rows):
    return plan_items_from_rows([
        {'id': r[0], 'taskId': r[1], 'prompt': 'p', 'verify': 'true',
         'candidates': ['m'], 'dependsOn': list(r[2:])} for r in rows
    ])


def task(citation, status='pending'):
    return {'citation': citation, 'native_status': status}


def test_settling_one_unit_offers_the_next_independent_one():
    items = plan(('a', 'TASK-API-0001'), ('b', 'TASK-API-0002'))
    report = classify(
        [task('TASK-API-0001'), task('TASK-API-0002')], items,
        {'a': 'accepted'})
    assert report['verdict'] == 'B'
    assert [unit['id'] for unit in report['frontier']] == ['b']


def test_an_exhausted_plan_with_a_pending_task_is_not_accepted():
    items = plan(('a', 'TASK-API-0001'))
    report = classify(
        [task('TASK-API-0001'), task('TASK-API-0002')], items,
        {'a': 'accepted'})
    assert report['verdict'] == 'C'
    assert report['unrepresented'] == ['TASK-API-0002']
    assert report['verdict'] != 'A'


def test_a_blocked_unit_does_not_hide_an_independent_one():
    items = plan(('a', 'TASK-API-0001'), ('b', 'TASK-API-0002'))
    report = classify(
        [task('TASK-API-0001'), task('TASK-API-0002')], items,
        {'a': 'blocked'})
    assert report['verdict'] == 'B'
    assert [unit['id'] for unit in report['frontier']] == ['b']
    assert report['blocked'] == [
        {'id': 'a', 'task': 'TASK-API-0001', 'reason': 'state blocked'}]


def test_a_dependency_not_accepted_is_named_as_the_blocking_reason():
    items = plan(('a', 'TASK-API-0001'), ('b', 'TASK-API-0001', 'a'))
    report = classify([task('TASK-API-0001')], items, {'a': 'failed'})
    reasons = {unit['id']: unit['reason'] for unit in report['blocked']}
    assert reasons['b'] == 'waits for a'


def test_settled_units_of_an_open_task_ask_for_closure_not_reimplementation():
    items = plan(('a', 'TASK-API-0001'))
    report = classify([task('TASK-API-0001')], items, {'a': 'accepted'})
    assert report['settled_task_open'] == ['TASK-API-0001']
    assert report['frontier'] == []
    assert report['verdict'] == 'C'


def test_everything_closed_is_a_candidate_never_an_acceptance():
    items = plan(('a', 'TASK-API-0001'))
    report = classify(
        [task('TASK-API-0001', 'completed')], items, {'a': 'accepted'})
    assert report['verdict'] == 'A'
    assert report['acceptance'] == 'requires executor authority (I-011)'


def obligation(module, category, task=None, symbol='S'):
    row = {'module': module, 'symbol': symbol, 'kind': 'method',
           'category': category}
    if task:
        row['task'] = task
    return row


def test_an_obligation_without_task_is_not_an_acceptance_candidate():
    items = plan(('a', 'TASK-API-0001'))
    report = classify(
        [task('TASK-API-0001', 'completed')], items, {'a': 'accepted'},
        [obligation('src/orm/fields.py', 'absent')])
    assert report['verdict'] == 'C'
    assert report['obligations_without_task'] == {'src/orm/fields.py': 1}


def test_an_empty_frontier_with_unverified_or_divergent_contracts_is_not_a():
    for category in ('not_verified', 'divergent'):
        report = classify([], plan(), {},
                          [obligation('src/orm/models.py', category)])
        assert report['verdict'] != 'A', category
        assert report['obligations'][category] == 1


def test_satisfied_obligations_alone_keep_the_candidate():
    report = classify([], plan(), {},
                      [obligation('src/orm/models.py', 'satisfied')])
    assert report['verdict'] == 'A'
    assert report['obligations']['pending'] == 0


def test_an_obligation_under_an_open_task_is_not_listed_as_without_task():
    items = plan(('a', 'TASK-API-0001'))
    report = classify(
        [task('TASK-API-0001')], items, {},
        [obligation('src/orm/models.py', 'absent', 'TASK-API-0001')])
    assert report['verdict'] == 'B'
    assert report['obligations_without_task'] == {}


def test_closing_the_task_does_not_satisfy_its_obligation():
    report = classify(
        [task('TASK-API-0001', 'completed')], plan(), {},
        [obligation('src/orm/models.py', 'absent', 'TASK-API-0001')])
    assert report['verdict'] == 'C'
    assert report['obligations_without_task'] == {'src/orm/models.py': 1}


def test_an_unknown_category_refuses_instead_of_counting_zero():
    try:
        classify([], plan(), {}, [obligation('m', 'probably_fine')])
    except ValueError as error:
        assert 'probably_fine' in str(error)
    else:
        raise AssertionError('an unknown category must refuse')


def test_a_task_with_several_units_stays_open_until_all_settle():
    items = plan(('a', 'TASK-API-0001'), ('b', 'TASK-API-0001', 'a'))
    report = classify([task('TASK-API-0001')], items, {'a': 'accepted'})
    assert report['settled_task_open'] == []
    assert [unit['id'] for unit in report['frontier']] == ['b']
    assert report['verdict'] == 'B'


def test_a_failed_unit_recovers_once_a_later_attempt_is_accepted():
    items = plan(('a', 'TASK-API-0001'), ('b', 'TASK-API-0002', 'a'))
    population = [task('TASK-API-0001'), task('TASK-API-0002')]
    failed = classify(population, items, {'a': 'failed'})
    assert {u['id']: u['reason'] for u in failed['blocked']} == {
        'a': 'state failed', 'b': 'waits for a'}
    recovered = classify(population, items, {'a': 'accepted'})
    assert [unit['id'] for unit in recovered['frontier']] == ['b']


def next_unit(bench):
    """La unidad que el controlador real del proveedor elige, sin juicio."""
    run = subprocess.run(['bash', CONTROLLER, 'next', str(bench)],
                         capture_output=True, text=True, check=True)
    return run.stdout.strip()


def test_settling_the_first_unit_lets_the_controller_select_the_second(
        tmp_path):
    rows = [{'id': unit, 'taskId': 'TASK-API-0001', 'prompt': 'p',
             'verify': 'true', 'candidates': ['m'], 'dependsOn': depends}
            for unit, depends in (('first', []), ('second', ['first']))]
    (tmp_path / 'plan.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows))
    assert next_unit(tmp_path) == 'first'
    append_log(tmp_path, {'kind': 'accepted', 'item': 'first',
                          'commitExit': 0})
    assert next_unit(tmp_path) == 'second'
