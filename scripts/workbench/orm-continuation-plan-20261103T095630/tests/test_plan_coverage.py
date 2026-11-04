"""Contrato de ``probes/plan_coverage.py``: frontera vacía no es aceptación.

La frontera de ``continuation_frontier.runnable_items`` sólo ve ``plan.jsonl``.
Estos casos fijan las tres situaciones que la iniciativa debe distinguir —A
criterios satisfechos, B trabajo pendiente y admisible, C trabajo pendiente sin
nada admisible— y que ninguna termine en ACCEPTED por un conteo en cero.
"""
import importlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'probes'))
sys.path.insert(0, '/home/user/thyrox/src')

classify = importlib.import_module('plan_coverage').classify
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
