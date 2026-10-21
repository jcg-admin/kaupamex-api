"""Actualiza observaciones sobre claves contractuales existentes; no crea población."""
import hashlib
import json
import subprocess
from pathlib import Path
root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
run=Path(__file__).resolve().parents[1];out=run/'outputs'
source=root/'scripts/evidence/orm-contract-plan-testorm-20261020T202537/outputs/functional-contract-coverage.json'
coverage=json.loads(source.read_text())
reports=json.loads((out/'scoped-test-results.json').read_text())['rows']
if (out/'incremental-test-results.json').exists():reports+=json.loads((out/'incremental-test-results.json').read_text())['rows']
history=json.loads((out/'github-history.json').read_text())
tasks=json.loads((out/'task-assessments.json').read_text())
groups=[]
for line in (run/'probes/group_findings.tsv').read_text().splitlines():
    index,paths,names,note=line.split('\t');original=coverage['full_module_characterizations'][int(index)]
    sources=[]
    for name in paths.split(';'):
        p=root/name;assert p.exists(),name
        sources.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None,'kind':'file' if p.is_file() else 'module directory; presence only, not conformance'})
    tests=[]
    for name in names.split(';') if names!='-' else []:
        path='tests/unit/orm/test_'+name+'.py'
        assert (root/path).is_file(),path
        observed=[r for r in reports if r['nodeid'].startswith(path+'::')]
        tests.append({'path':path,'current_pytest_reports':observed,'unit_log':'retry-final.log (16PGPASS)' if name=='missing_recompute' else None,'prior_pg_evidence':'orm-as-is-reconciliation-20261021T164519/outputs/relational-persistence.log (5PASS)' if name=='relational_reconstruction_persistence' else None,'unexecuted_limit':None if observed or name in ('missing_recompute','relational_reconstruction_persistence') else 'Named suite exists; not executed in scoped312-case batch. Required dataset/runtime and behavior in finding; not a PASS.'})
    groups.append({'source_group':original['source_group'],'reference_contract_authority':str(source.relative_to(root))+'#full_module_characterizations/'+original['source_group'],'reference_contract_14_elements':original['contract'],'current_consumer_sources':sources,'specific_finding':note,'tests':tests,'native_odoo_execution':'NOT_EVALUATED; no native Odoo runtime/fixtures started','whole_group_acceptance':'not established by bounded subcontracts; acceptance requires applicable source assertions and stated Consumer conditions'})
assert len(groups)==66
map_groups={
 'record_identity_singleton':[7], 'exists_recordset_semantics':[18,19],
 'cache_value_and_miss':[10],'cache_across_user_environments':[10],'selective_invalidation':[42],
 'row_rule_access':[4], 'cursor_transaction_lifecycle':[12], 'cursor_replica_selection':[12],
 'inverse_dependency_navigation':[8], 'domain_any_rights_optimization':[41],
 'invalidate_all_flush_before_invalidate':[42], 'flush_recompute_fixpoint':[12],
 'relational_field_reconstruction':[2,26], 'recompute_dependent_record_discovery':[1,9],
 'translated_record_storage_query':[54], 'company_relation_consistency':[30,31],
 'domain_null_boolean_partition':[44], 'protected_compute_scope':[9],
 'json_value_isolation_roundtrip':[55], 'relation_command_membership':[21,48],
 'virtual_onchange_delta':[57], 'prefetch_batch_reuse':[18,47],
 'property_definition_authority':[32,33], 'field_storage_reflection':[61],
 'relational_domain_query_semantics':[41,44], 'recordset_sort_order':[46],
 'web_projection_access':[63], 'record_attribute_boundary':[51], 'autovacuum_expiration':[52],
 'index_method_reconciliation':[53], 'float_render_precision':[59],
 'browser_x2many_constraint_integration':[62], 'default_view_field_projection':[64]}
notes={
 'exists_recordset_semantics':'El caso vacío existe; la suite312 no observa existentes/nuevos/id0 con PG. QuerySet.exists devuelve bool y no puede sustituir recordset exists sin adaptación. BaseModel.new falta; no se acepta esa rama por browse.',
 'cursor_transaction_lifecycle':'El probePG histórico de cursor/rollback se reutiliza; el batch312 verifica Transaction en memoria. Ownership/nesting/callbacks de cursor necesitan prueba real aislada; no se aceptan desde Cache.clear.',
 'cursor_replica_selection':'La comparación previa de seis escenarios del cuerpo detecta diferencias cooldown/thread/ProgrammingError. Sigue sin réplica real y sin TASK atómica reconciliada; fallback disponible no implica equivalencia.',
 'invalidate_all_flush_before_invalidate':'Defecto previo demostrado: invalidate_all ignora flush. No se encontró identidad atómica equivalente en la consulta nativa documentada; GEN0575 completed no autoriza asignarle esta corrección.',
 'cache_value_and_miss':'La lectura/escritura de caché de campo y Transaction se ejecutó en suites seleccionadas; las28operaciones de Cache no están todas ejecutadas. CacheMiss se distingue de valorFalse, y prueba de facade requiere su suite específica.',
 'cache_across_user_environments':'Cache es transaccional, pero dos uid con campos name/ref set-overwrite-remove y contexto sensible requieren fixture explícito. No se presupone partición/compartición por compartir objeto Transaction.',
 'selective_invalidation':'Pruebas de cache/Transaction ejecutadas cubren borrado selectivo de entradas; composición exacta dos campos/dos registros y todos los contextos requiere escenario de referencia. No se sustituye por invalidación total.',
 'relational_field_reconstruction':'Se conserva6c11ddde y sus8casos más5PG históricos. Nuevo diff sólo modifica recompute/imports, no el algoritmo de reconstrucción; no repetir pruebas válidas ni aceptar M2M/O2O persistente por FK.',
 'recompute_dependent_record_discovery':'Se cerró la brecha acotada de0559 con16PGPASS, incluyendo filas ausentes al consultar/durantecompute, error persistente,related ausente,virtual,AccessError y managerpúblico.7de8casos nuevos fallan con Field.recompute99f restaurado; no acepta batching ni toda cadena0424.',
 'translated_record_storage_query':'Divergencia histórica varchar/jsonb conservada. GEN0060/0062 y flag0283 son obligaciones distintas; la migración permanece no autorizada. No se computa cobertura funcional desde presencia translate.',
 'json_value_isolation_roundtrip':'0420 preserva literal e independencia de default,serialización y PGJSONB previos; actual regresión pasa7JSON. Json copy-on-read/normalización general no se declara aceptado. CI bloquea cuerpos por setup, no prueba fallos JSON.',
 'field_storage_reflection':'DDL por tipo/columna, reflexión y catalogación aún requiere PG real de schema axis. La FK temporal0419 o un field con store=True no satisface ese contrato completo.'}
descriptors=[]
for original in coverage['records']:
    name=original['descriptor'];ids=map_groups[name]
    descriptors.append({'descriptor':name,'authority':str(source.relative_to(root))+'#records/'+name,'reference_contract_14_elements':original['contract'],'related_source_groups':[groups[i]['source_group'] for i in ids],'specific_finding':notes.get(name,' '.join(groups[i]['specific_finding'] for i in ids)),'consumer_evidence':[{'sources':groups[i]['current_consumer_sources'],'tests':groups[i]['tests']} for i in ids],
      'task_links':original['contract'].get('existing_task_relationships'),'acceptance':'Bounded observed behavior only; no whole descriptor acceptance from presence or filenames.'})
assert len(descriptors)==33
# Enlazar hechos remotos reales, sin convertir asociación commit/PR en aceptación TASK.
for task in tasks['tasks']:
    shas={c['sha'] for c in task['task_mentioned_commits']+task['commits_explicit_in_native_description']}
    shas.update(s['last_matching_line_change_commit'] for s in task['source_evidence'] if s.get('last_matching_line_change_commit'))
    shas.update(s['head_body_last_change_commit'] for s in task['source_evidence'] if s.get('head_body_last_change_commit'))
    task['publication_and_ci']={sha:history['commits'][sha] for sha in sorted(shas)}
    task['history_search_result']='No citation-tagged commit found in fetched local refs; source-touch/native-description evidence is distinct.' if not task['task_mentioned_commits'] else 'Explicit citation mentions located; file changes and PR/CI must be reviewed before asserting implementation acceptance.'
result={'reference_revision':coverage['revision'],'population_authority':str(source.relative_to(root)),'descriptors':descriptors,'source_groups':groups,'tasks':tasks['tasks'],'legacy_resolution':tasks['legacy_resolution'],'observed_develop':tasks['observed_develop_revision'],'scope_limit':'Individual analysis of existing scope, not whole ORM conformance or new canonical backlog. Every unexecuted obligation has its own behavior/fixture condition, no generic default finding.'}
(out/'contractual-assessments.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# Implementation AS IS y reconciliación contractual','','Se conserva la población y sus14elementos; aquí se distinguen comportamiento observado, candidato y condición de verificación.','',
'## Obligaciones existentes','', '| Descriptor | Hallazgo individual |','|---|---|']
for r in descriptors:lines.append('| '+r['descriptor']+' | '+r['specific_finding'].replace('|','/')+' |')
lines+=['','## Caracterizaciones completas de test_orm','']
for r in groups:lines += ['### '+r['source_group'],'',r['specific_finding'],'','Consumer: '+', '.join(s['path'] for s in r['current_consumer_sources'])+'.',
 'Verificadores: '+', '.join(t['path']+(' — ejecutado (ver outcomes por nodeid)' if t['current_pytest_reports'] else ' — ver evidencia/condición individual, no PASS por existencia') for t in r['tests']) if r['tests'] else 'Verificador Consumer de este comportamiento aún por delimitar con los fixtures y criterio descritos; no se excluye el contrato.','']
(out/'implementation-assessments.md').write_text('\n'.join(lines)+'\n')
print('Individual contractual assessments:',len(descriptors),'descriptors,',len(groups),'source groups;',len(tasks['tasks']),'TASK with actual GitHub PR/check observations')
