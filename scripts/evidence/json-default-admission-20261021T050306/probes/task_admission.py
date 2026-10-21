"""Lee identidad y dependencias crudas con interfaces nativas; nunca migra."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from agents.agent_store import connect_readonly, resolve_store_dir
from session.claim_fold import active_claims
from task.task_ids import lookup, mapping_from_store


home = resolve_store_dir(argparse.Namespace(claude_dir=None, repo=None), create=False)
database = home / 'agent_store.sqlite3'
before = hashlib.sha256(database.read_bytes()).hexdigest()
connection = connect_readonly(home)
row = dict(connection.execute(
    'SELECT * FROM tasks WHERE citation_id=?', ('TASK-API-0420',)
).fetchone())
assert lookup(mapping_from_store(database), row['session_id'], row['task_id']) == row['citation_id']
related = [dict(x) for x in connection.execute(
    "SELECT citation_id,subject,description,status,owner,blocks_json,blocked_by_json "
    "FROM tasks WHERE session_id=? AND (citation_id=? OR blocks_json LIKE ?)",
    (row['session_id'], 'TASK-API-0416', '%1195%'),
)]
invalidations = [dict(x) for x in connection.execute(
    "SELECT citation_id,subject FROM tasks WHERE "
    "lower(subject || ' ' || coalesce(description,'')) LIKE '%invalidate_all%' "
    "OR lower(subject || ' ' || coalesce(description,'')) LIKE '%flush_all%'"
)]
connection.close()
after = hashlib.sha256(database.read_bytes()).hexdigest()
assert before == after
claims = {}
for name in ('kaupamex-api', 'thyrox'):
    ledger = Path('/workspace') / name / '.claude/coordination/claims.jsonl'
    claims[name] = active_claims([
        json.loads(line) for line in ledger.read_text().splitlines() if line.strip()
    ])
result = {
    'interface': 'resolve_store_dir(create=False), connect_readonly, mapping_from_store, lookup; active_claims',
    'provider_revision': subprocess.check_output(
        ['git', '-C', '/workspace/thyrox', 'rev-parse', 'HEAD'], text=True
    ).strip(),
    'row': row,
    'related_rows': related,
    'invalidate_all_exact_text_matches': invalidations,
    'claims': claims,
    'sha256_before': before,
    'sha256_after': after,
    'store_unchanged': True,
    'admission': 'BLOCKED',
    'blocker': 'Operational owner NULL; no native TASK ownership assignment authorized or performed. NULL dependencies are not proof of satisfied functional dependencies.',
    'preparation_claim_is_not_task_assignment': True,
}
out = Path(__file__).resolve().parents[1] / 'outputs/task-admission.json'
out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({k: result[k] for k in (
    'provider_revision', 'store_unchanged', 'admission', 'blocker'
)}, ensure_ascii=False, indent=2))
