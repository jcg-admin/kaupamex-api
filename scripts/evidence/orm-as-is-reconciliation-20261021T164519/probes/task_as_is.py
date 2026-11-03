"""Vista AS IS del Consumer sobre población existente; no gestor ni selector nuevo."""
import argparse
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path

provider = Path(os.environ['THYROX_ROOT']).resolve()
sys.path.insert(0, str(provider / 'src'))
from agents.agent_store import connect_readonly, resolve_store_dir
from session.claim_fold import active_claims
from task.task_ids import lookup, mapping_from_store
from task.task_source import records_from_store
from task.implementation_order import build_edges
from session.continuation_frontier import runnable_items
from session.job_runs import jobs_dir
from workbench.manifest import read_manifest_file, resolve_manifest

root = Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
out = Path(__file__).resolve().parents[1] / 'outputs'
base = root / 'scripts/evidence'
plan_path = base / 'orm-contract-plan-20261020T202045/outputs/population-population-and-units.json'
coverage_path = base / 'orm-contract-plan-testorm-20261020T202537/outputs/functional-contract-coverage.json'
prior_path = base / 'authority-separation-20261021T012957/outputs/task-reconciliation.json'
plan = json.loads(plan_path.read_text())
coverage = json.loads(coverage_path.read_text())
prior = json.loads(prior_path.read_text())
citations = set(re.findall(r'TASK-[A-Z]+-\d+', json.dumps([plan, coverage, prior])))
store_dir = resolve_store_dir(argparse.Namespace(claude_dir=None,repo=None),create=False)
store = store_dir / 'agent_store.sqlite3'
before = hashlib.sha256(store.read_bytes()).hexdigest()
mapping = mapping_from_store(store)
scope_doc = root.parent / 'kaupamex-docs/source/gestion/pm/api/iniciativas/completar-raiz-orm/tareas-completar-raiz-orm.rst'
historical_refs = []
for ordinal in sorted(set(re.findall(r'^- \*\*#(\d+)\*\*',scope_doc.read_text(),re.M)),key=int):
    citation = lookup(mapping,'29a5e555-e34f-5a20-8c39-ad6cf2f19961',ordinal)
    historical_refs.append({'ordinal':ordinal,'session_checked':'29a5e555-e34f-5a20-8c39-ad6cf2f19961','citation':citation,'limit':'No fallback to another session; unresolved legacy citation is not a missing implementation'})
    if citation:
        citations.add(citation)
conn = connect_readonly(store_dir)
rows = [dict(r) for r in conn.execute('SELECT * FROM tasks WHERE citation_id IN (' + ','.join('?' for _ in citations) + ')', sorted(citations))]
# Revisión acotada de identidad para brechas ya demostradas; no inventario global.
related = [dict(r) for r in conn.execute("SELECT citation_id,session_id,task_id,subject,description,status,owner,blocked_by_json FROM tasks WHERE subject LIKE '%invalidate_all%' OR subject LIKE '%apply_except_missing%' OR subject LIKE '%res_users%' OR subject LIKE '%setup%' OR subject LIKE '%0419%'")]
conn.close()
claims = {}
for name, repo in [('api',root),('docs',root.parent/'kaupamex-docs'),('thyrox',provider)]:
    ledger = repo / '.claude/coordination/claims.jsonl'
    claims[name] = active_claims([json.loads(s) for s in ledger.read_text().splitlines() if s.strip()])
    for c in claims[name]:
        c['process_liveness'] = 'not_verified across agents/VMs; claim alone is not progress'
projected = {layer: records_from_store(store,layer=layer) for layer in ('api','gen','thyrox')}
projection = {row['citation']: row for layer in projected.values() for row in layer}
for row in rows:
    assert lookup(mapping,row['session_id'],str(row['task_id'])) == row['citation_id']
    row['active_claims'] = [c for cs in claims.values() for c in cs if c.get('task')==row['citation_id']]
    row['dependencies_projection'] = projection.get(row['citation_id'],{}).get('blockedBy')
    row['acceptance'] = 'not_verified from native status; see contract reconciliation'
# Ejercita el grafo nativo sin parchear la proyección ni inferir admisión.
edges, provenance = build_edges({p['citation']:p for p in projection.values() if p['citation'] in citations})
interfaces = {'provider_revision':subprocess.check_output(['git','-C',str(provider),'rev-parse','HEAD'],text=True).strip(),
 'command':'THYROX_ROOT=<declared-provider> uv run --frozen python <run>/probes/task_as_is.py',
 'used':['resolve_store_dir(create=False)','connect_readonly','mapping_from_store/lookup','records_from_store(api/gen/thyrox)','build_edges','active_claims','jobs_dir/resolve_manifest/read_manifest_file'],
 'frontier':{'signature':str(inspect.signature(runnable_items)),'availability':'pure existing bank PlanItem mechanism; no accepted executable bank for this analytical population; not invoked, no synthetic acceptance'},
 'planning_projection':{'edge_count':sum(map(len,edges.values())),'provenance':dict(provenance),'qualification':'not qualified for admission: reader hardcodes blockedBy=[] and omits descriptions. Known1072, foreign claim preserved; raw dependency source retained below.'}}
job_state = {}
for name, repo in [('api',root),('docs',root.parent/'kaupamex-docs'),('thyrox',provider)]:
    home=jobs_dir(repo)
    # Sólo jobs recuperados por esta iniciativa, no barrido de toda telemetría.
    prefixes=('orm-','json-','relational-field-','babok-')
    job_state[name]=[]
    if home.exists():
        for run in sorted(home.iterdir()):
            m=resolve_manifest(run) if run.is_dir() and run.name.startswith(prefixes) else None
            if m:
                v=read_manifest_file(m)
                job_state[name].append({'run':run.name,'exit_code':v.get('exit_code'),'started_at':v.get('started_at'),'liveness':'not_verified; missing settlement does not establish active execution'})
result={'population_sources':[str(p.relative_to(root)) for p in (plan_path,coverage_path,prior_path)],
 'historical_scope_refs':historical_refs,'selected_citations':sorted(citations),'native_rows':rows,'missing_citations':sorted(citations-{r['citation_id'] for r in rows}),
 'related_existing_rows':related,'claims':claims,'jobs':job_state,'interfaces':interfaces,
 'store_sha256_before':before,'store_sha256_after':hashlib.sha256(store.read_bytes()).hexdigest()}
assert result['store_sha256_before']==result['store_sha256_after']
(out/'task-as-is.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lineage={}
for f in [plan_path,coverage_path,prior_path]:
    lineage[str(f.relative_to(root))]=hashlib.sha256(f.read_bytes()).hexdigest()
lineage['implementation_revision']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
lineage['changed_since_population']=subprocess.check_output(['git','diff','--name-only',plan['input_revisions']['api'],'HEAD','--','src/orm','tests/unit/orm'],text=True).splitlines()
(out/'input-lineage.json').write_text(json.dumps(lineage,indent=2)+'\n')
print(json.dumps({'existing_descriptors':len(coverage['records']),'scoped_task_rows':len(rows),'missing':result['missing_citations'],'native_claims':{k:len(v) for k,v in claims.items()},'store_unchanged':True,'projection_qualified_for_admission':False}))
for row in sorted(rows,key=lambda r:r['citation_id']):
    print(row['citation_id'],row['status'],row['owner'],row['subject'])
for row in related:print('RELATED',row['citation_id'],row['subject'])
