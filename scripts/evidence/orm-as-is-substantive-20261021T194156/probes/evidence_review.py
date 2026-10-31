"""Revisión Consumer por TASK: usa lectores/procedencia existentes; no decide estados."""
import argparse
import ast
import tempfile
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

provider=Path(os.environ['THYROX_ROOT']).resolve()
root=Path(subprocess.check_output(['git','rev-parse','--show-toplevel'],text=True).strip())
sys.path[:0]=[str(provider/'src'),str(root/'scripts')]
from agents.agent_store import resolve_store_dir,connect_readonly
from task.task_ids import mapping_from_store,lookup
from session.claim_fold import active_claims
from counterpart_body import declarations_of

run=Path(__file__).resolve().parents[1];out=run/'outputs'
prior=root/'scripts/evidence/orm-as-is-reconciliation-20261021T164519/outputs/task-as-is.json'
original=json.loads(prior.read_text());extra=json.loads((out/'incremental-existing-task-links.json').read_text())
selected=original['selected_citations']+[r['citation_id'] for r in extra]
store_dir=resolve_store_dir(argparse.Namespace(claude_dir=None,repo=None),create=False)
store=store_dir/'agent_store.sqlite3';before=hashlib.sha256(store.read_bytes()).hexdigest()
connection=connect_readonly(store_dir);mapping=mapping_from_store(store)
rows={r['citation_id']:dict(r) for r in connection.execute('SELECT * FROM tasks WHERE citation_id IN ('+','.join('?' for _ in selected)+')',selected)}
legacy=[]
for old in original['historical_scope_refs']:
    if old['citation']:continue
    candidates=[dict(r) for r in connection.execute('SELECT citation_id,session_id,task_id,board_ordinal,subject FROM tasks WHERE task_id=? OR board_ordinal=?',(old['ordinal'],int(old['ordinal'])))]
    legacy.append({'original_reference':old,'native_candidates_all_sessions':candidates,'decision':'No original-session identity matches. Candidates are different coordinates, not an authorized mapping. Preserve ordinal; connect related contract separately, do not select by numeric coincidence.'})
connection.close()
claims={}
for label,path in [('api',root),('docs',root.parent/'kaupamex-docs'),('thyrox',provider)]:
    p=path/'.claude/coordination/claims.jsonl'
    claims[label]=active_claims([json.loads(s) for s in p.read_text().splitlines() if s.strip()])
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
develop=subprocess.check_output(['git','rev-parse','origin/develop'],text=True).strip()
messages=subprocess.check_output(['git','log','--all','--format=%H%x1f%B%x1e'],text=True)
commits=[]
for entry in messages.split('\x1e'):
    if '\x1f' in entry:
        sha,body=entry.strip().split('\x1f',1);commits.append((sha,body))
cache={};ancestry={};revision_cache={}
def revision_declarations(relative,ref):
    key=(relative,ref)
    if key not in revision_cache:
        result=subprocess.run(['git','show',ref+':'+relative],text=True,capture_output=True)
        if result.returncode:
            revision_cache[key]=[]
        else:
            with tempfile.NamedTemporaryFile(mode='w',suffix='.py') as f:
                f.write(result.stdout);f.flush();revision_cache[key]=declarations_of(f.name)
    return revision_cache[key]

def contained(sha):
    if sha not in ancestry:
        ancestry[sha]={ref:subprocess.run(['git','merge-base','--is-ancestor',sha,ref],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode for ref in [head,develop]}
    return {'in_working_head':ancestry[sha][head]==0,'in_observed_develop':ancestry[sha][develop]==0,'ancestor_exit_codes':ancestry[sha]}
def locate(relative,symbol):
    path=(root/relative).resolve();text=path.read_text();lines=text.splitlines()
    assert symbol in text,(relative,symbol)
    if path not in cache:cache[path]=declarations_of(path)
    decls=[d for d in cache[path] if d.name==symbol]
    if decls:
        d=decls[-1];start=d.lineno;end=getattr(d.node,'end_lineno',start)
        evidence={'kind':d.kind,'owner':d.owner,'start':start,'end':end,'body':'\n'.join(lines[start-1:end])}
    else:
        hits=[i for i,l in enumerate(lines,1) if symbol in l]
        evidence={'kind':'literal references; not asserted to be a definition','lines':hits,'contexts':[{'start':max(1,i-2),'text':'\n'.join(lines[max(0,i-3):i+3])} for i in hits[:12]]}
    history=subprocess.check_output(['git','log','-1','--format=%H','-G',re.escape(symbol),'--',relative],text=True).strip() if not relative.startswith('../') else ''
    if decls and not relative.startswith('../'):
        evidence['declaration_comparison']={}
        for ref in (head,develop):
            previous=[x for x in revision_declarations(relative,ref) if x.name==d.name and x.owner==d.owner]
            evidence['declaration_comparison'][ref]=bool(previous and ast.dump(previous[-1].node,include_attributes=False)==ast.dump(d.node,include_attributes=False))
            if ref==head and previous:
                previous=previous[-1]
                query=['git','log','-1','--format=%H','--no-patch','-L',f'{previous.lineno},{previous.node.end_lineno}:{relative}']
                result=subprocess.run(query,text=True,capture_output=True)
                evidence['head_body_history_command']=query
                evidence['head_body_history_exit']=result.returncode
                evidence['head_body_last_change_commit']=result.stdout.strip() if result.returncode==0 else None
                if evidence['head_body_last_change_commit']:
                    evidence['head_body_last_change_containment']=contained(evidence['head_body_last_change_commit'])
    evidence.update(path=relative,symbol=symbol,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),last_matching_line_change_commit=history or None)
    if history:evidence['matching_line_change_containment']=contained(history)
    return evidence
suite=json.loads((out/'scoped-test-results.json').read_text())['rows']
if (out/'incremental-test-results.json').exists():suite+=json.loads((out/'incremental-test-results.json').read_text())['rows']
findings=[]
for line in (run/'probes/task_findings.tsv').read_text().splitlines():
    citation,locations,tests,observation,next_action=line.split('\t');native=rows[citation]
    assert lookup(mapping,native['session_id'],str(native['task_id']))==citation
    sources=[locate(*loc.split(':',1)) for loc in locations.split(';')]
    matched=[{'sha':sha,'subject':body.splitlines()[0],**contained(sha)} for sha,body in commits if re.search(r'(?<![\w-])'+re.escape(citation)+r'(?![\w-])',body)]
    explicit=[]
    for token in set(re.findall(r'\b[0-9a-f]{7,40}\b',native['description'] or '')):
        result=subprocess.run(['git','rev-parse','--verify',token+'^{commit}'],text=True,capture_output=True)
        if result.returncode==0:
            sha=result.stdout.strip();explicit.append({'sha':sha,'source':'native task description',**contained(sha)})
    deps=json.loads(native['blocked_by_json'] or 'null') or []
    dependencies=[{'raw':str(dep),'same_session_identity':lookup(mapping,native['session_id'],str(dep)),'note':'Raw coordinate resolved only in native session; absence of an edge does not prove independence'} for dep in deps]
    test_details=[]
    for name in tests.split(';') if tests!='-' else []:
        p=root/'tests/unit/orm'/(name+'.py');assert p.is_file(),p
        results=[x for x in suite if x['nodeid'].startswith(str(p.relative_to(root))+'::')]
        test_details.append({'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'current_observed_reports':results,'execution':'Executed named cases; see phase/outcome' if results else 'Not executed in312-case unit batch. Relevant verifier located; DB/startup/resource preconditions in next_action, not counted as PASS.'})
    findings.append({'citation':citation,'native_identity':{'session_id':native['session_id'],'task_id':native['task_id']},'official_status':native['status'],'official_owner':native['owner'],
      'claims':[c for cs in claims.values() for c in cs if c.get('task')==citation],
      'dependency_sources':{'raw':native['blocked_by_json'],'resolved_native_edges':dependencies,'functional_conditions':next_action},
      'scope_source':{'native_subject':native['subject'],'native_description':native['description'],'additional_authority':'Existing completar-raiz-orm scope and source contract comments; missing native description not silently replaced.'},
      'source_evidence':sources,'task_mentioned_commits':matched,'history_limit':'Citation is navigational, not acceptance. -G changes matching lines, not whole function. Body -L history and declaration comparisons are recorded separately; source identity still is not conformance.',
      'commits_explicit_in_native_description':explicit,'tests':test_details,'observed_conclusion':observation,'next_action':next_action,
      'verification_and_acceptance':'Specific current test outcomes above; full TASK acceptance is not inferred. Unit0559 additionally16PostgreSQL PASS; baseline7/8 retry failures plus alias-specific negative1error.',
      'integration_rule':'Containment measured separately for every linked commit against fixed remote develop SHA; code may later be changed/reverted, so ancestry is not current semantic acceptance.'})
assert len(findings)==len(rows)==60
assert hashlib.sha256(store.read_bytes()).hexdigest()==before
result={'consumer_revision':head,'provider_revision':subprocess.check_output(['git','-C',str(provider),'rev-parse','HEAD'],text=True).strip(),'observed_develop_revision':develop,'reference_revision':'abe4040ec1a45beee90fb694e4eae4453e46b389','store_sha256':before,'store_unchanged':True,'tasks':findings,'legacy_resolution':legacy,'claims':claims,'working_diff':subprocess.check_output(['git','diff','--','src/orm/fields.py','tests/unit/orm/test_missing_recompute.py'],text=True),'source_scope':'Existing55identities plus5existing citations found in current ORM/tests; not new tasks or backlog. Each conclusion manually reviewed; code extraction/history/tests are evidence, not automatic defect or readiness classification.'}
(out/'task-assessments.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
review=['# Revisión individual TASK AS IS','','Head '+head+'; develop observado '+develop+'. La pertenencia de commits no sustituye verificación de conducta.','']
for f in findings:
    review += ['## '+f['citation']+' — '+f['scope_source']['native_subject'],'',
       'Estado nativo: '+f['official_status']+'; owner: '+str(f['official_owner'])+'. Identidad '+str(f['native_identity'])+'.',
       '',f['observed_conclusion'],'','Siguiente condición: '+f['next_action'],'',
       'Fuente: '+', '.join(s['path']+':'+s['symbol'] for s in f['source_evidence'])+'.',
       'Commits con cita explícita: '+str(len(f['task_mentioned_commits']))+'; detalle y pertenencia a develop en task-assessments.json. No se equiparan a aceptación.',
       'Verificadores: '+', '.join(t['path']+' ('+t['execution']+')' for t in f['tests']) if f['tests'] else 'Verificador específico por delimitar según condición anterior; no se afirma ausencia por el estado nativo.','']
(out/'task-assessments.md').write_text('\n'.join(review)+'\n')
print(json.dumps({'individual_assessments':len(findings),'source_spans':sum(len(f['source_evidence']) for f in findings),'linked_task_citation_commits':sum(len(f['task_mentioned_commits']) for f in findings),'legacy_coordinates_investigated':len(legacy),'store_unchanged':True,'develop':develop}))
