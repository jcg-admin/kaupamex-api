"""Incremento idempotente del AS IS existente para TASK-API-0382; no inventario global."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
run = Path(__file__).resolve().parent.parent
label = str(run.relative_to(root))
outputs = root/'scripts/evidence/orm-as-is-substantive-20261021T194156/outputs'
native = json.loads(json.loads((run/'outputs/native-task-0382.json').read_text())['content'])
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
paths = ['task-assessments.json', 'contractual-assessments.json',
         'task-assessments.md', 'implementation-assessments.md']
inputs = {name: hashlib.sha256((outputs/name).read_bytes()).hexdigest() for name in paths}
if not (run/'outputs/as-is-input-hashes.json').exists():
    (run/'outputs/as-is-input-hashes.json').write_text(json.dumps(inputs, indent=2)+'\n')
sources = []
for name, symbols in [
    ('src/addons/base/management/commands/update_module_list.py', ['handle', '_refresh', '_sync_dependencies']),
    ('src/addons/base/models/ir_module.py', ['_request_module_change', '_walk_dependencies', '_compute_depend_batch'])]:
    p = root/name
    text = p.read_text()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name in symbols:
            sources.append({'path': name, 'symbol': node.name, 'start': node.lineno,
                            'end': node.end_lineno, 'source_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                            'body': ast.get_source_segment(text, node)})
record = {
    'citation': native['citation_id'],
    'native_identity': {'session_id': '168b0fdf-bfe4-590b-b6c0-b6be124c124a', 'task_id': native['task_id']},
    'official_status': native['status'], 'official_owner': native['owner'],
    'claims': ['Native claimsCommand; ledger .claude/coordination/claims.jsonl; own scope only'],
    'dependency_sources': {'raw': native['blocked_by'], 'resolved_native_edges': native['blocked_by'],
                           'functional_conditions': 'DEC-AISL-05 accepted; installed state != schema != effective registry. Native TASK-API-0173 pending/unowned is related, not automatically eligible.'},
    'scope_source': {'native_subject': native['subject'], 'native_description': native['description'],
                     'additional_authority': 'User continuation of complete module lifecycle document; admission-continuation.json'},
    'source_evidence': sources,
    'task_mentioned_commits': [], 'commits_explicit_in_native_description': [],
    'history_limit': 'Incremental source and runtime evidence at the recorded revision; not a new exhaustive historical search.',
    'tests': ['tests/integration/base/test_module_catalog_database.py',
              'tests/integration/base/test_module_state_requests.py',
              label+'/probes/database_module_states.py'],
    'observed_conclusion': 'Catalogue refresh no longer derives operational states from imported apps. Administrative requests validate dependencies/authorization, lock and queue transitions in one database. Two real databases retain distinct states, concurrent requests and rollback; mixed-database batches with colliding IDs are rejected. Installation itself is not executed by these requests.',
    'next_action': 'Complete effective registry and schema/data/hooks loader using existing mechanisms. Global automation signals still lose explicit DB alias on metadata writes; prototype isolated process composition is not production integration. TASK-API-0173 identity checked; no arbitrary relocation of capability identities or historical migration rewrite.',
    'verification_and_acceptance': label+'/outputs: baseline 5FAIL/1PASS; old report fixture 84PASS/1FAIL retained and corrected with explicit installed-state fixture plus negative case; definitive rerun and ci-verify recorded separately. No whole TASK acceptance.',
    'integration_rule': 'Existing feature branch/PR109; no merge or official TASK state change.',
    'publication_and_ci': 'Functional source revision '+head+' plus recorded working changes; see final README and PR109 for publication/CI outcome.',
    'history_search_result': 'Prior AS IS retained; module-lifecycle and current scoped native exports reused.'}
for name in ['task-assessments.json', 'contractual-assessments.json']:
    path = outputs/name
    data = json.loads(path.read_text())
    existing = next((i for i, row in enumerate(data['tasks']) if row['citation']==native['citation_id']), None)
    if existing is None:
        data['tasks'].append(record)
    else:
        data['tasks'][existing] = record
    for related in data['tasks']:
        if related['citation']=='TASK-API-0417':
            marker = ' Incremento compute-boundary: '
            related['observed_conclusion'] = related['observed_conclusion'].split(marker)[0]+marker+label+' demonstrates that generic DisplayNameMixin and ProductProduct both return values instead of assigning display_name. The real descriptor raises ValueError for both; assignment-only controls pass. Earlier bounded compute results do not imply all display_name Consumers conform.'
            related['next_action'] = 'Reconcile existing generic display-name contract and Consumer overrides without restoring the retired constructor dispatcher or weakening assignment checks. Native TaskGet1192 confirms in_progress/owner null; not automatically eligible. Preserve module-lifecycle priority and CI failure.'
    if name=='contractual-assessments.json':
        group = next(row for row in data['source_groups'] if row['source_group']=='model_registry_extension_semantics')
        marker = ' Incremento module-state: '
        group['specific_finding'] = group['specific_finding'].split(marker)[0]+marker+label+' verifies database-owned pending requests, not complete lifecycle. Fresh processes can compose distinct models/extensions using native Apps, but model checks reject base without authz; native auto-install closure passes model checks. Signals/global runtime and persistent loader integration remain pending.'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
marker = '\n## Incremento module-state\n'
for name in ['task-assessments.md','implementation-assessments.md']:
    path = outputs/name
    prior = path.read_text().split(marker)[0]
    path.write_text(prior+marker+'\nTASK-API-0382, sesión168b0fdf-bfe4-590b-b6c0-b6be124c124a/local737, conserva pending y owner codex-module-lifecycle. Se añade sólo este registro al alcance histórico; no se considera la población exhaustiva.\n\n'+record['observed_conclusion']+'\n\n'+record['next_action']+'\n\nEvidencia y resultados definitivos: '+label+'/README.md. Sin aceptación integral ni merges.\n')
# Actualizar sólo hashes de los cuatro artefactos afectados; conservar otros registros.
sums = outputs/'SHA256SUMS'
lines = []
for line in sums.read_text().splitlines():
    digest, sep, name = line.partition('  ')
    target = outputs/Path(name).name
    if target.name in paths and target.is_file():
        line = hashlib.sha256(target.read_bytes()).hexdigest()+sep+name
    lines.append(line)
sums.write_text('\n'.join(lines)+'\n')
print('Updated one native TASK and one existing source group; original population not regenerated')
