import argparse,json,hashlib,subprocess
from pathlib import Path
from agents.agent_store import resolve_store_dir,connect_readonly
from task.task_ids import mapping_from_store,lookup
from session.claim_fold import active_claims
from session.job_runs import jobs_dir
from workbench.manifest import read_manifest_file
out=Path('/workspace/scratch/authority-separation'); home=resolve_store_dir(argparse.Namespace(claude_dir=None,repo=None),create=False); db=home/'agent_store.sqlite3'; before=hashlib.sha256(db.read_bytes()).hexdigest(); conn=connect_readonly(home)
def forbid(action,*args):
 import sqlite3
 return sqlite3.SQLITE_DENY if action in [sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,sqlite3.SQLITE_CREATE_TABLE,sqlite3.SQLITE_DROP_TABLE,sqlite3.SQLITE_ALTER_TABLE] else sqlite3.SQLITE_OK
conn.set_authorizer(forbid)
columns=[dict(x) for x in conn.execute('PRAGMA table_info(tasks)')]; tables=[x['name'] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]; schema={t:conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()[0] for t in ['tasks','schema_migrations'] if t in tables}
citations=['TASK-API-'+n for n in ['0216','0283','0397','0398','0400','0402','0406','0417','0418','0419','0420','0421','0424','0427']]+['TASK-GEN-'+n for n in ['0060','0062','0507','0508','0558','0559','0575','0578']]+['TASK-THYROX-1072']
mapping=mapping_from_store(db); rows=[]
for citation in citations:
 q=conn.execute('SELECT * FROM tasks WHERE citation_id=?',(citation,)).fetchall()
 for raw in q:
  row=dict(raw); row['resolved_citation']=lookup(mapping,row['session_id'],str(row['task_id'])); row['functional_owner']='kaupamex-api candidate from functional contract, not operational owner' if citation.startswith(('TASK-API','TASK-GEN')) else 'thyrox'; row['functional_owner_limit']='GEN scope/iniciative must be read; prefix is not final repository adjudication'; rows.append(row)
state={'path':str(db),'read_interface':'resolve_store_dir(create=False),connect_readonly + SQL reads guarded by authorizer; mapping_from_store/lookup','provider_revision':subprocess.check_output(['git','-C','/workspace/thyrox','rev-parse','HEAD'],text=True).strip(),'schema':schema,'task_columns':columns,'tables':tables,'selected_tasks':rows,'hash_before':before,'hash_after':hashlib.sha256(db.read_bytes()).hexdigest(),'query_only_reads':True,'no_migration_or_store_copy':True}
if 'schema_migrations' in tables: state['migration_ledger']=[dict(x) for x in conn.execute('SELECT * FROM schema_migrations')]
conn.close(); assert state['hash_before']==state['hash_after']; (out/'store-readonly.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
repos=[]
for name in ['kaupamex-api','kaupamex-docs','kaupamex-db','kaupamex-server','kaupamex-ui','thyrox']:
 root=Path('/workspace')/name; ledger=root/'.claude/coordination/claims.jsonl'; claims=active_claims([json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]) if ledger.exists() else []
 jhome=jobs_dir(root); jobrows=[]
 if not jhome.is_absolute(): jhome=root/jhome
 if jhome.exists():
  for f in sorted(jhome.glob('*/manifest.jsonl')):
   m=read_manifest_file(f); jobrows.append({'run':f.parent.name,'manifest':m})
 repos.append({'repo':name,'claims':claims,'job_home':str(jhome),'jobs':jobrows})
(out/'claims-jobs.json').write_text(json.dumps(repos,ensure_ascii=False,indent=2,default=str)+'\n')
print(json.dumps({'store':str(db),'selected_tasks':len(rows),'schema_version_rows':len(state.get('migration_ledger',[])),'hash_unchanged':True,'claims':{x['repo']:len(x['claims']) for x in repos},'jobs':{x['repo']:len(x['jobs']) for x in repos}},indent=2))
