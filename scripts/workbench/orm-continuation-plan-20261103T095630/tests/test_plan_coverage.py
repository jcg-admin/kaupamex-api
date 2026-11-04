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

coverage = importlib.import_module('plan_coverage')
classify = coverage.classify
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


def owned_plan(*rows):
    """Unidades que declaran ``owned``: lo que el claim ajeno compara."""
    return plan_items_from_rows([
        {'id': r[0], 'taskId': r[1], 'prompt': 'p', 'verify': 'true',
         'candidates': ['m'], 'dependsOn': [], 'owned': list(r[2])}
        for r in rows])


def foreign(path, owner='codex-module-lifecycle', task_id='TASK-API-0267'):
    return [{'path': path, 'owner': owner, 'task': task_id}]


def test_a_unit_claimed_by_another_owner_leaves_the_frontier():
    items = owned_plan(('a', 'TASK-API-0001', ['src/x.py']),
                       ('b', 'TASK-API-0002', ['src/y.py']))
    report = classify([task('TASK-API-0001'), task('TASK-API-0002')], items,
                      {}, foreign=foreign('src/x.py'))
    assert [unit['id'] for unit in report['frontier']] == ['b']
    assert report['blocked'] == [{
        'id': 'a', 'task': 'TASK-API-0001',
        'reason': 'claimed by codex-module-lifecycle (TASK-API-0267) on '
                  'src/x.py'}]


def test_the_foreign_claims_skip_the_own_owner():
    rows = [{'id': '1', 'op': 'claim', 'path': 'src/x.py',
             'owner': 'VM-x2hokp', 'task': 'TASK-API-0001'},
            {'id': '2', 'op': 'claim', 'path': 'src/y.py',
             'owner': 'codex-module-lifecycle', 'task': 'TASK-API-0267'}]
    assert [claim['path'] for claim in coverage.foreign_claims(
        rows, 'x2hokp')] == ['src/y.py']


def test_a_settled_unit_outside_the_integration_branch_is_listed():
    items = plan(('a', 'TASK-API-0001'), ('b', 'TASK-API-0001'))
    report = classify([task('TASK-API-0001')], items,
                      {'a': 'accepted', 'b': 'accepted'}, integrated={'a'})
    assert report['settled_not_integrated'] == ['b']


def test_unmeasured_integration_is_not_reported_as_integrated():
    report = classify([], plan(), {})
    assert report['settled_not_integrated'] is None


def test_a_scope_task_represents_the_obligations_of_its_directory():
    report = classify(
        [], plan(), {}, [obligation('src/tools/zeep/client.py', 'absent'),
                         obligation('src/tools/misc.py', 'absent')],
        scopes={'src/tools/zeep': {'TASK-API-0491'}},
        store_open={'TASK-API-0491'})
    assert report['obligation_classes'] == {
        'task_without_unit': 1, 'unrepresented': 1}
    assert report['obligations_without_task'] == {'src/tools/misc.py': 1}
    assert report['verdict'] == 'C'


def test_a_candidate_task_is_not_a_representation():
    report = classify(
        [], plan(), {}, [obligation('src/orm/models.py', 'absent')],
        candidates=lambda row: {'TASK-API-0397'},
        store_open={'TASK-API-0397'})
    assert report['obligation_classes'] == {'candidate_task': 1}
    assert report['obligations_without_task'] == {'src/orm/models.py': 1}


def test_an_applicable_obligation_survives_an_exhausted_plan():
    """La TASK de alcance existe y no tiene unidad: el plan se agota y la
    obligación sigue contando como pendiente, y el dictamen nunca es A."""
    items = plan(('a', 'TASK-API-0001'))
    report = classify(
        [task('TASK-API-0001', 'completed')], items, {'a': 'accepted'},
        [obligation('src/orm/fields.py', 'not_verified')],
        scopes={'src/orm': {'TASK-API-0485'}}, store_open={'TASK-API-0485'})
    assert report['frontier'] == []
    assert report['obligations']['pending'] == 1
    assert report['obligation_classes'] == {'task_without_unit': 1}
    assert report['verdict'] == 'C'


def test_the_scope_subject_is_an_exact_declaration():
    tasks = [('TASK-API-0491', 'Cerrar las obligaciones estructurales '
              'pendientes de src/tools/zeep', ''),
             ('TASK-API-0399', 'Revisar src/tools/zeep de paso', '')]
    assert coverage.scope_links(tasks) == {'src/tools/zeep': {'TASK-API-0491'}}
