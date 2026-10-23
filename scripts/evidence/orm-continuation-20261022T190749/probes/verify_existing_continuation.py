"""Consumer qualification of existing Thyrox interfaces; isolated fixtures only.

No scheduler, acceptance policy or production TASK state is implemented here.
This cannot intercept the Codex host's final response. It verifies observable
continuation decisions of the native controller that the Consumer now calls.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from session import task_continuation
from session.continuation_frontier import item_states

OUT = Path(__file__).resolve().parents[1] / 'outputs/continuation-controls.json'
ROWS = [
    {'id': 'ModuleGraph.reference_inventory', 'prompt': 'inventory.md',
     'verify': 'true', 'route': 'local', 'taskId': 'TASK-API-0382',
     'dependsOn': [], 'mutates': False, 'owned': ['reference_inventory']},
    {'id': 'ModuleNode.phase', 'prompt': 'phase.md', 'verify': 'true',
     'route': 'local', 'taskId': 'TASK-API-0382', 'dependsOn': [],
     'mutates': False, 'owned': ['src/modules/module_graph.py']},
]


def main():
    plan = task_continuation.plan_items_from_rows(ROWS)
    accepted = {'kind': 'accepted', 'item': ROWS[0]['id']}
    results = []
    for name, log in [
        ('pilot_done_work_remains', [accepted]),
        ('commit_is_not_objective_acceptance', [accepted, {'kind': 'commit', 'item': ROWS[1]['id']}]),
        ('failed_acceptance_does_not_block_independent_unit', [
            {'kind': 'hard_block', 'item': ROWS[0]['id']}]),
    ]:
        selected = task_continuation.node_frontier(plan, item_states(log), set(), [], 'b501')
        assert [entry.id for entry in selected] == [ROWS[1]['id']], name
        results.append({'control': name, 'fixture_log': log,
                        'selected': selected[0].id, 'objective_complete': False})

    blocked = dict(ROWS[0], dependsOn=[ROWS[1]['id']])
    dependent_plan = task_continuation.plan_items_from_rows([blocked, ROWS[1]])
    selected = task_continuation.node_frontier(dependent_plan, {}, set(), [], 'b501')
    assert [e.id for e in selected] == [ROWS[1]['id']]
    results.append({'control': 'blocked_first_selects_independent_second', 'selected': selected[0].id})
    claims = [{'op': 'claim', 'owner': 'vm-other', 'path': 'src/modules', 'task': 'fixture'}]
    selected = task_continuation.node_frontier(plan, {ROWS[0]['id']: 'accepted'}, set(), claims, 'b501')
    assert selected == []
    results.append({'control': 'no_admissible_due_to_foreign_claim', 'selected': [],
                    'objective_complete': False, 'reason': 'Foreign path reservation, not missing obligations'})

    with tempfile.TemporaryDirectory(prefix='orm-continuation-control-') as name:
        bank = Path(name)
        (bank / 'plan.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in ROWS))
        task_continuation.append_log(bank, accepted)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = task_continuation.main(['next', str(bank), '--local-only'])
        assert code == 0 and output.getvalue().strip() == ROWS[1]['id']
        # Reload from disk; do not retain in-memory states for resumption.
        restored = task_continuation.read_log(bank)
        assert len(restored) == 1
        assert restored[0]['kind'] == accepted['kind']
        assert restored[0]['item'] == accepted['item']
        assert 'utc' in restored[0] and 'epoch' in restored[0]
        results.append({'control': 'resumption_from_native_plan_and_log',
                        'output': output.getvalue().strip(), 'exit_code': code})

        # Negative mutation: fabricate all accepted only inside this fixture.
        # The same assertion must reject the native CLI's premature completion.
        with patch.object(task_continuation, 'item_states', return_value={
                row['id']: 'accepted' for row in ROWS}):
            with contextlib.redirect_stdout(io.StringIO()) as corrupted:
                task_continuation.main(['next', str(bank), '--local-only'])
        detected = corrupted.getvalue().strip() != ROWS[1]['id']
        assert detected and corrupted.getvalue().strip() == 'plan completo'
        results.append({'control': 'premature_completion_mutation_detected',
                        'mutated_output': corrupted.getvalue().strip(), 'detected': detected})

    OUT.write_text(json.dumps({'interface': 'native node_frontier/main next/read_log',
        'provider_revision': '9b13f2d7a1f070bfd293f9fb8acc7c4ea8f9555f',
        'fixture_only': True, 'production_task_writes': False,
        'limits': 'Verifies bounded native plan continuation; does not qualify absent goal API, local inference, global plan coverage or enforce Codex host termination',
        'controls': results}, indent=2) + '\n')
    print(f'{len(results)} continuation controls PASS, including resumption and negative mutation')


if __name__ == '__main__':
    main()
