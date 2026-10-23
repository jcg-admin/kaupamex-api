"""Incremental source-reviewed dispositions; reuse the owner inventory unchanged."""
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parents[1]
INVENTORY = REPO / 'scripts/workbench/odoo-orm-reference-inventory-20260910T181517'
spec = importlib.util.spec_from_file_location('existing_inventory', INVENTORY / 'inventory_reference_orm.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

# Explicit reviewed correspondence, not a second resolver. Each tuple records
# behavior, current mechanism, verification, and the specific remaining boundary.
REVIEW = {
 'ModuleNode': ('Manifest/dependency node plus database load snapshot and computed ordering/phase/demo attributes',
    'src/modules/module_graph.py::ModuleNode; base.IrModule catalogue',
    'Current constructor/property controls; native metadata inspection',
    'id, installed_version, load_state/load_version snapshot binding not implemented'),
 'ModuleNode.__init__': ('Input name and graph; resolve/parse manifest; initialize id0, uninstalled states, demoFalse, versionNone and empty dependency set',
    'ModuleNode.__init__; modules.module.load_manifest; IrModule persisted state outside graph',
    'Demo/state defaults exercised by new graph fixtures; manifest constructor reference not executed',
    'Consumer stores dependency names immediately and lacks reference id/version/load snapshot attributes; native manifest lifecycle not_verified'),
 'ModuleNode.order_name': ('Normal name unchanged; test_* uses greatest dependency by depth/order key followed by space and own name; no anchor raises ValueError',
    'ModuleNode.order_name; ModuleGraph._depth',
    'test_ordinary_depth_and_order_key_agree; test_test_addon_placement_matches_reference; test_test_addon_ties_and_nested_anchors; empty/cycle/mutation controls',
    'Bounded value conformance; Odoo cached_property invalidation lifecycle and complete executable loader not accepted'),
 'ModuleNode.depth': ('Normal node returns max dependency depth+1 or0; test_* shares greatest dependency depth; empty test dependency set raises ValueError',
    'ModuleNode.depth -> ModuleGraph._depth',
    'Pinned class differential controls; existing graph diamond/cycle/single-evaluation/mutation tests',
    'Consumer raises explicit ModuleGraphCycle instead of reference graph prune policy; load graph pruning pending'),
 'ModuleNode.phase': ('base0; load mode nonbase1; update mode max(dependency phase + to-install XOR + base dependency bonus); empty update anchor raises ValueError',
    'ModuleNode.phase -> ModuleGraph._phase; explicit ModuleGraph.mode and ModuleNode.state',
    'test_reference_phase_depends_on_mode_and_pending_state; four state-boundary/iteration cases; invalid-mode, cycle and empty-anchor controls',
    'Phase arithmetic implemented for explicit nodes only; no database snapshot or actual phase execution; cached descriptor semantics not accepted'),
 'ModuleNode.demo_installable': ('Return all dependency demo flags, vacuously True without dependencies; no mutation or database write',
    'ModuleNode.demo_installable; ModuleNode.demo=False default',
    'test_demo_eligibility_is_dependency_based: empty positive, false negative, enable and disable after observation',
    'Does not read per-database demo state, load demo data, or accept data-loader behavior'),
 'ModuleGraph': ('Cursor-bound mode-aware module set supports dependency preparation, state filtering, pruning and ordered loading',
    'ModuleGraph static/explicit-mode graph plus separate IrModule catalogue/requests',
    'Graph protocol and ordering/phase controls; prior two-database catalogue evidence',
    'No cursor/database binding; full class equivalence not_verified; migration execution is separate'),
 'ModuleGraph.__init__': ('Retain cursor, load/update mode and empty module mapping; default load',
    'ModuleGraph.__init__(*, mode="load") validates mode and creates _nodes',
    'No-argument existing regression fixtures; update constructor/invalid mode controls',
    'No cursor/alias parameter or selected-database snapshot; signature adapted, not globally equivalent'),
 'ModuleGraph.__contains__': ('Input module name; Boolean membership in graph mapping; no mutation',
    'ModuleGraph.__contains__ -> _nodes',
    'test_static_graph_membership_lookup_and_cardinality: present/absent controls',
    'Verified static protocol only; membership of database-filtered graph pending'),
 'ModuleGraph.__getitem__': ('Input module name; return its node or raise KeyError; no mutation',
    'ModuleGraph.__getitem__ -> _nodes',
    'test_static_graph_membership_lookup_and_cardinality: lookup and missing KeyError',
    'Verified static protocol only; graph contents differ until load filtering exists'),
 'ModuleGraph.__iter__': ('Return iterator sorted by phase, depth and dependency-aware order_name; no persistent state changes',
    'ModuleGraph.__iter__ -> _depth/_phase/ModuleNode.order_name -> CPython sorted',
    'Pinned state-boundary and test-addon ordered output comparisons, plus existing cycle/diamond tests',
    'Explicit-state arithmetic/order verified; database-derived states, imported modules and pruning still pending'),
 'ModuleGraph.__len__': ('Return cardinality of current graph mapping without mutation or IO',
    'ModuleGraph.__len__ -> _nodes',
    'test_static_graph_membership_lookup_and_cardinality',
    'Does not establish correct database-specific population'),
 'ModuleGraph.extend': ('Reset existing node cached properties; add only requested new names; prune un-installable nodes; update dependency links/depth/database state',
    'ModuleGraph.extend transitive static closure; IrModule._request_module_change validates metadata and queues states separately',
    'Existing dependency/cycle/auto-install tests; prior database request tests; not reference extend conformance',
    'Reference explicitly requested nodes differ from Consumer transitive closure; no graph DB filter, imported exception or recursive prune. Requests do not execute installs'),
 'ModuleGraph._imported_modules': ('Cache ordered names studio_customization plus database imported rows when optional imported column exists',
    'No demonstrated equivalent; module get_modules enumerates code, not imported database modules',
    'test_reference_imported_modules_optional_column_and_cache:2PASS; imported-module-contract.json actual Consumer model metadata without DB IO',
    'Optional-column/query/order/cache reference controls verified with mocked cursor; Consumer imported provenance producer/field and native DB fixture absent. No Consumer equivalence; remains pending0382'),
 'ModuleGraph._update_depends': ('Resolve declared dependencies to nodes already in graph; missing dependency removes node and dependent nodes',
    'ModuleGraph._update_depends -> _remove; IrModule administrative dependency validation remains separate',
    'test_missing_dependency_prunes_dependents_and_retains_independent_node; published baseline negative',
    'Explicit pure graph preparation verified; static extend retains its existing transitive/rejecting policy; DB-bound loader wiring pending'),
 'ModuleGraph._update_depth': ('Force depth evaluation for new nodes; on recursive cycle remove affected node and its dependents',
    'ModuleGraph._update_depth -> _depth -> _remove; static order/cycles still reject/diagnose explicitly',
    'test_explicit_depth_preparation_prunes_cycles_like_reference; existing public static cycle tests; published baseline negative',
    'Explicit pure preparation verified; no claim static extend or DB loading automatically invokes prune preparation'),
 'ModuleGraph._update_from_database': ('Select name,id,state,demo,latest_version AS installed_version for retained new nodes; prune uninstallable always and uninstalled/to-install in load; copy snapshot and load-state/version',
    'base.IrModule state/demo catalogue; update_module_list metadata refresh; graph has explicit state/demo but no snapshot query',
    'snapshot-metadata.json real Django model fields; manifest-version-control.json; prior two-database state/request evidence',
    'version stores manifest metadata and is refreshed even for installed rows; cannot infer installed version. No full faithful snapshot, load filtering or version migration accepted'),
 'ModuleGraph._remove': ('Remove named node and recursively remove graph nodes depending on it; optional logging affects diagnostics, not selection',
    'ModuleGraph._remove, called by explicit _update_depends/_update_depth; string dependencies adapt reference node identity',
    'test_recursive_removal_matches_reference[True/False]; test_removing_absent_node_rejects_both_graphs; published baseline negative',
    'Pure closure/diagnostics verified on equal ordered input mappings; no database uninstall, schema removal or loader binding accepted'),
 'ModuleNode.phase.not_in_the_same_phase': ('Boolean XOR of module and dependency state equal to to install; pure nested helper used by phase',
    'Inline XOR-equivalent inequality in ModuleGraph._phase, distributed from ModuleNode.phase',
    'Four state-boundary comparisons and phase mutation controls',
    'Pure explicit-state truth table verified; database snapshot integration pending'),
}


def main():
    previous = json.loads((INVENTORY / 'outputs/module-graph-pilot.json').read_text())
    reference = inventory.TREE_ROOTS['odoo19c'] / 'odoo/modules/module_graph.py'
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == previous['reference_sha256']
    rows = []
    for name, (behavior, mechanism, verification, remaining) in REVIEW.items():
        historic = next((r for r in previous['correspondence'] if r['qualified_name'] == name), None)
        rows.append({
            'reference_revision': previous['reference_revision'],
            'reference_symbol': 'odoo/modules/module_graph.py::' + name,
            'behavior': behavior,
            'execution_flow': mechanism,
            'inputs_outputs': historic['source_header'] if historic else '(module: ModuleNode, dependency: ModuleNode) -> bool',
            'side_effects': 'As specified in behavior; graph construction/state reads and pruning are not equivalent to administrative catalogue writes',
            'dependencies': ['Existing ModuleNode/ModuleGraph/manifest parser', 'TASK-API-0382', remaining],
            'consumers': ['Reference ModuleGraph.extend/iteration and module loader', mechanism],
            'installed_mechanism': mechanism,
            'existing_adaptation': 'Qualified correspondence above; source-header/signature from historical pinned pilot, not simple-name matching',
            'verification': {'specific_controls': verification, 'current_evidence': str(RUN.relative_to(REPO)),
                             'positive_negative_limits': remaining},
            'equivalence': 'Bounded observations only; not_verified for remaining contract',
            'limitations': remaining,
            'integration': {'task': 'TASK-API-0382', 'official_status': 'pending',
                            'acceptance': 'not_verified', 'merge': False, 'PR': 109},
        })
    assert len(rows) == 19
    target = INVENTORY / 'outputs/module-graph-contract-reconciliation.json'
    target.write_text(json.dumps({
        'extends': 'module-graph-pilot.json',
        'reference_inventory': 'module-graph-pilot.json#reference_inventory; unchanged source hash verified, no duplicate extraction',
        'supplemental_reference': 'module-graph-pilot.json#supplemental_source_review; conditional alias/imports/logger/bases/attributes retained',
        'consumer_inventory': inventory.file_inventory(REPO / 'src/modules/module_graph.py'),
        'consumer_sha256': hashlib.sha256((REPO / 'src/modules/module_graph.py').read_bytes()).hexdigest(),
        'named_reference_declarations': len(rows),
        'contract_records': rows,
        'supplemental_dispositions': {
            'STATES': 'Conditional type alias, not a persisted enum; IrModule.STATES is existing choice metadata. Whole vocabulary compatibility remains not_verified.',
            '_logger': 'Consumer logger now emits explicit prune diagnostics. Removal logs verified against reference for equal ordered mappings. Imported-module logging/loader context still pending.',
            'imports': 'Historical ledger distinguishes runtime imports from TYPE_CHECKING imports. CPython functools.cached_property differs from Consumer property; fresh values tested, cache lifecycle not accepted.',
            'dynamic_definitions': 'No class factory/metaclass/overload declarations in this pinned file; cached descriptors and nested phase helper explicitly accounted for. Lambda/local bindings remain in source, not new durable contract IDs.',
            'consumer_nested': 'ModuleGraph.cycles.walk and ModuleNode.__slots__ remain Consumer-only source-reviewed declarations outside the historical extractor.',
        },
        'scope': 'One unchanged reference file and changed Consumer counterpart; not global ORM coverage',
        'acceptance': 'No file-level contract acceptance. Pending symbols remain visible; completed0391/0392 are instrument TASKs only.',
    }, indent=2, ensure_ascii=False) + '\n')
    print(f'Updated changed Consumer inventory; {len(rows)} qualified reference dispositions linked to existing pilot')


if __name__ == '__main__':
    main()
