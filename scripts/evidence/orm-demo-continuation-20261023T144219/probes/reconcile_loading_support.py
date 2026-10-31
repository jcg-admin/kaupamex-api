"""Incremental Consumer contract evidence; no TASK/state or planning authority."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
JOB = Path(__file__).resolve().parents[1]
BANK = ROOT/'scripts/workbench/odoo-orm-reference-inventory-20260910T181517'
spec = importlib.util.spec_from_file_location('owner_inventory', BANK/'inventory_reference_orm.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
source = owner.TREE_ROOTS['odoo19c']/'odoo/modules/loading.py'
path = BANK/'outputs/loading-contract-reconciliation.json'
data = json.loads(path.read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest() == data['reference_sha256']
expected = subprocess.check_output(['git', 'show', '56c6d4ea:src/modules/loading.py'], cwd=ROOT)
assert (ROOT/'src/modules/loading.py').read_bytes() == expected, 'Requalify changed loading code first'
summary_path = JOB/'outputs/loading-support-summary.json'
summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
declarations = owner.declared_symbols(source)
records = []
for name in ['_check_module_names', 'reset_modules_state']:
    declaration = next(row for row in declarations if row['name'] == name)
    names = name == '_check_module_names'
    record = {
        'reference_revision': data['reference_revision'],
        'reference_symbol': 'odoo/modules/loading.py::'+name,
        'source_location': declaration['lineno'], 'owner': 'odoo.modules.loading',
        'symbol_kind': 'function',
        'behavior': 'Warn only unknown requested module names without writes' if names else
                    'Restore transient requests after failed installation, preserving stable states and versions',
        'execution_flow': ['Deduplicate iterable', 'Discard all wildcard', 'Count names in selected catalogue',
                           'Read actual catalogue only on mismatch and warn unknown names'] if names else
                          ['Require caller failure transaction exited', 'Begin native atomic recovery',
                           'Missing catalogue is no-op', 'Restore removal/upgrade to installed and install to uninstalled',
                           'Commit both or roll back both on error'],
        'inputs_outputs': {'source_signature': declaration['signature'],
                           'consumer_signature': '(cr, module_names)' if names else '(using)',
                           'result': 'None; errors propagate'},
        'side_effects': 'Read SQL and warning only; no mutation of input or states' if names else
                        'Two bounded state updates and commit; no installed_version update or actual installation',
        'dependencies': ['Supplied native Django cursor', 'Existing selected PostgreSQL catalogue'] if names else
                        ['Declared Django connection alias', 'Autocommit outside caller atomic',
                         'Django introspection and transaction.atomic; no effective registry needed'],
        'consumers': ['Pinned load_modules; Consumer outer loader still unintegrated'] if names else
                     ['Pinned Registry failure recovery; Consumer Registry.new still calls _ensure_seeded'],
        'installed_mechanism': 'src/modules/loading.py::'+name,
        'existing_adaptation': 'psycopg3 = ANY(list) replaces psycopg2 IN(tuple); fetchall replaces dictfetchall' if names else
                               'Explicit alias replaces db name. Django root atomic replaces independent Odoo cursor; nesting/manual transaction refused. Both updates atomic.',
        'verification': {'focused': 'Six red controls -> PASS' if names else 'Four red controls -> PASS',
                         'combined': '26PASS data/demo/names/reset',
                         'postgresql': '16 source differential catalogue cases, two isolated schemas, unchanged states and parameterized injection string' if names else
                                       'Six state mappings match pinned function, unchanged versions, committed visibility from second connection, missing table, nested refusal, actual second-update constraint rollback',
                         'negative': 'No-op in memory exits1 expected',
                         'evidence': str(JOB.relative_to(ROOT))},
        'equivalence': 'Bounded differential PASS with real PG and explicit cursor-protocol adaptation; native Odoo runtime not executed',
        'limitations': 'No outer-loader integration, effective per-base model composition, complete company provisioning or TASK acceptance. Two schemas in one database are not N>1 productive acceptance.',
        'integration': {'task': 'TASK-API-0382', 'code_commit': '56c6d4ea',
                        'acceptance': 'not_verified', 'merge': False, 'official_state_changes': False},
    }
    if summary.get('integration', {}).get('published'):
        record['integration']['published'] = True
    ci = summary.get('ci', {}).get('exact_code_revision', {})
    if ci.get('state') == 'completed':
        record['verification']['ci'] = ci
    records.append(record)
symbols = {row['reference_symbol'] for row in records}
data['contract_records'] = [r for r in data['contract_records'] if r['reference_symbol'] not in symbols]+records
data['other_named_declarations_pending'] = [r for r in data['other_named_declarations_pending']
                                            if r['name'] not in ['_check_module_names', 'reset_modules_state']]
data['consumer_loading_inventory'] = owner.file_inventory(ROOT/'src/modules/loading.py')
data['consumer_loading_sha256'] = hashlib.sha256((ROOT/'src/modules/loading.py').read_bytes()).hexdigest()
data['scope'] = 'Five reviewed source-flow contracts; force_demo and load_modules remain pending. Symbol/file counts do not establish contractual acceptance coverage.'
data['current_support_evidence'] = str(JOB.relative_to(ROOT))+'/outputs/loading-support-summary.json'
path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
base = ROOT/'scripts/evidence/orm-as-is-substantive-20261021T194156/outputs'
for name in ['task-assessments.json', 'contractual-assessments.json']:
    target = base/name
    document = json.loads(target.read_text())
    assert len(document['tasks']) == 62
    row = next(r for r in document['tasks'] if r['citation'] == 'TASK-API-0382')
    previous = row.get('current_loading_support', {})
    row['current_loading_support'] = {
        'code_commit': '56c6d4ea', 'contracts': sorted(symbols),
        'verification': '26 focused PASS, actual PostgreSQL differentials PASS, both negative no-ops exit1 expected',
        'evidence': str(JOB.relative_to(ROOT))+'/outputs/loading-support-summary.json',
        'task_state': 'pending; owner codex-module-lifecycle; no TaskUpdate',
        'acceptance': 'not_verified; outer caller integration and full goal remain unaccepted',
    }
    for key in ['ci', 'published']:
        if key in previous:
            row['current_loading_support'][key] = previous[key]
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n')
print('Updated existing loading ledger and same 62-task AS IS population')
