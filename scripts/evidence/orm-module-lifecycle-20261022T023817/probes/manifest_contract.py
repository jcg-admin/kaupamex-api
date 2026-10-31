"""Manifiestos y candidatos auto_install: declaraciones frente a efectos."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from modules import module_graph
from modules.module import load_manifest, check_python_external_dependency, MissingDependency

run = Path(__file__).resolve().parent.parent
fixture = {'name': 'Fixture', 'version': '1.0', 'license': 'LGPL-3', 'depends': ['base'],
           'auto_install': [], 'installable': False, 'application': True,
           'external_dependencies': {'python': ['json']},
           'pre_init_hook': 'pre', 'post_init_hook': 'post', 'uninstall_hook': 'remove'}
with tempfile.TemporaryDirectory(prefix='module-manifest-') as directory:
    path = Path(directory)
    manifest = path / '__manifest__.py'
    manifest.write_text(repr(fixture))
    observed = load_manifest('fixture', directory)
    keys = ('depends', 'auto_install', 'installable', 'application',
            'external_dependencies', 'pre_init_hook', 'post_init_hook', 'uninstall_hook')
    retained = {key: observed.get(key) for key in keys}
    assert retained == {key: fixture[key] for key in keys}
    marker = path / 'must_not_execute'
    manifest.write_text(f"__import__('pathlib').Path({str(marker)!r}).touch()")
    try:
        load_manifest('fixture', directory)
    except ValueError:
        rejected_code = True
    else:
        rejected_code = False
    assert rejected_code and not marker.exists()

check_python_external_dependency('json')
try:
    check_python_external_dependency('orm_contract_dependency_that_does_not_exist')
except MissingDependency:
    missing_dependency_rejected = True
else:
    missing_dependency_rejected = False
assert missing_dependency_rejected
manifest_map = {'base': {'depends': []},
                'bridge': {'depends': ['base'], 'auto_install': []},
                'disabled': {'depends': [], 'installable': False}}
with patch.object(module_graph, 'load_manifest', side_effect=lambda name: manifest_map[name]):
    graph = module_graph.ModuleGraph()
    graph.extend(list(manifest_map))
    auto_candidates = graph.auto_installable([])
    disabled_in_static_graph = 'disabled' in graph

result = {'manifest_properties_retained': retained, 'executable_manifest_rejected': rejected_code,
          'missing_python_dependency_rejected': missing_dependency_rejected,
          'auto_install_empty_trigger': {'inputs': manifest_map, 'present': [],
              'observed_candidates': auto_candidates, 'expected_candidate': 'bridge',
              'candidate_requirement_satisfied': 'bridge' in auto_candidates,
              'reference': 'Odoo modules/db.py initialize: auto_install is not False; empty required subset qualifies.'},
          'disabled_module_in_static_graph': disabled_in_static_graph,
          'limitations': 'Static graph inclusion is not installation. Retaining hook keys does not execute hooks; no loader or dependency admission is qualified by this parser probe.'}
(run / 'outputs' / 'manifest-contract.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
