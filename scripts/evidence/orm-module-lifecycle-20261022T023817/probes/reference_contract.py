"""Fuente contractual fijada y llamadas ejecutables; no usa cabeceras como prueba."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
sys.path.insert(0, str(root / 'scripts'))
from reference_roots import tree, TOOLS_ROOT

run = Path(__file__).resolve().parent.parent
revision = 'abe4040ec1a45beee90fb694e4eae4453e46b389'
reference = tree('odoo19c')
selected = {
    'odoo/orm/registry.py': ['Registry.new', 'Registry.init', 'Registry.load', 'Registry.check_signaling'],
    'odoo/modules/module_graph.py': ['ModuleGraph.extend', 'ModuleGraph._update_depends',
                                    'ModuleGraph._update_depth', 'ModuleGraph._update_from_database'],
    'odoo/modules/loading.py': ['load_modules', 'load_module_graph'],
    'odoo/modules/db.py': ['initialize', 'is_initialized'],
    'odoo/modules/module.py': ['load_manifest', 'load_openerp_module'],
    'odoo/addons/base/models/ir_module.py': ['IrModuleModule.button_install', 'IrModuleModule.button_upgrade',
                                           'IrModuleModule.button_uninstall', 'IrModuleModule.module_uninstall'],
}


def symbols(path):
    found = {}
    def visit(body, prefix=''):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + node.name
                calls = []
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        calls.append({'line': child.lineno, 'call': ast.unparse(child.func)})
                found[name] = {'line': node.lineno, 'end_line': node.end_lineno,
                               'signature': ast.unparse(node.args) if hasattr(node, 'args') else None,
                               'calls': calls}
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + '.')
    visit(ast.parse(path.read_text()).body)
    return found


records = []
prior = run / 'outputs' / 'reference-source.json'
verified = {r['path']: r for r in json.loads(prior.read_text())} if prior.exists() else {}
for relative, names in selected.items():
    path = reference / relative
    relative_repo = path.relative_to(TOOLS_ROOT)
    endpoint = f'repos/jcg-admin/odoo-tools/contents/{relative_repo}?ref={revision}'
    command = ['gh', 'api', endpoint, '--jq', '.sha']
    local_blob = hashlib.sha1(b'blob ' + str(path.stat().st_size).encode() + b'\0' + path.read_bytes()).hexdigest()
    cached = verified.get(relative)
    if cached and cached['git_blob'] == local_blob and cached['revision'] == revision:
        exit_code = cached['exit_code']
    else:
        result = subprocess.run(command, capture_output=True, text=True)
        exit_code = result.returncode
        assert exit_code == 0 and result.stdout.strip() == local_blob, (relative, exit_code)
    source_symbols = symbols(path)
    records.append({'path': relative, 'revision': revision, 'command': command,
                    'exit_code': exit_code, 'git_blob': local_blob,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'symbols': {name: source_symbols.get(name, {'status': 'symbol_not_found'}) for name in names}})
    print('Verified fixed reference blob:', relative, local_blob, flush=True)
(run / 'outputs' / 'reference-source.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')

consumer_paths = ['src/orm/routers.py', 'src/orm/registry.py', 'src/modules/module.py',
                  'src/modules/module_graph.py', 'src/service/db.py',
                  'src/addons/base/models/ir_module.py', 'src/addons/base/models/ir_model.py',
                  'src/addons/base/management/commands/update_module_list.py']
consumer = {}
for relative in consumer_paths:
    path = root / relative
    all_symbols = symbols(path)
    if relative.endswith('ir_model.py'):
        all_symbols = {name: value for name, value in all_symbols.items() if '_module_data_uninstall' in name}
    consumer[relative] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'symbols': all_symbols}

definitions = {}
hook_calls = []
for prefix in ('src', 'addons'):
    for path in (root / prefix).rglob('*.py'):
        if 'migrations' in path.parts:
            continue
        try:
            parsed = ast.parse(path.read_text())
        except (SyntaxError, UnicodeError):
            continue  # silent OK because los archivos no analizables se excluyen de esta búsqueda, no se califican conformes.
        for node in ast.walk(parsed):
            if isinstance(node, ast.FunctionDef) and node.name in (
                    'load_modules', 'load_module_graph', 'button_install', 'button_upgrade', 'button_uninstall'):
                definitions.setdefault(node.name, []).append([str(path.relative_to(root)), node.lineno])
            if isinstance(node, ast.Call) and ast.unparse(node.func).split('.')[-1] in (
                    'pre_init_hook', 'post_init_hook', 'uninstall_hook'):
                hook_calls.append([str(path.relative_to(root)), node.lineno, ast.unparse(node.func)])
observation = {'consumer_base_revision': 'f04dfd1b9884998996bff8161f4962cea7f7fb7c',
               'files': consumer, 'lifecycle_entry_definitions': definitions, 'literal_hook_calls': hook_calls,
               'search_limitation': 'No name match is not proof against indirect dispatch. Read Registry.new/load and update_module_list bodies and use runtime registry/state experiment for the conclusion.'}
(run / 'outputs' / 'consumer-source.json').write_text(json.dumps(observation, ensure_ascii=False, indent=2) + '\n')
print('Consumer lifecycle entry definitions:', definitions)
print('Literal hook calls:', hook_calls)
