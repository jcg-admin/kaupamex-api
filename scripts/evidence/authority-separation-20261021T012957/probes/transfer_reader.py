import json,sys,hashlib,subprocess
from pathlib import Path
from agents.agent_store import connect_readonly
from task.task_ids import mapping_from_store,lookup
from session.claim_fold import active_claims
p=json.loads(Path(sys.argv[1]).read_text()); home=Path(p['store']); c=connect_readonly(home); mapping=mapping_from_store(home/'agent_store.sqlite3'); rows=[]
for ref in p['tasks']:
 row=c.execute('SELECT citation_id,session_id,task_id,subject,status,owner,blocked_by_json FROM tasks WHERE session_id=? AND task_id=?',(ref['session'],ref['task'])).fetchone(); assert row is not None; row=dict(row); assert lookup(mapping,ref['session'],ref['task'])==ref['citation']; rows.append(row)
c.close(); evidence=Path(p['evidence']['path']); assert hashlib.sha256(evidence.read_bytes()).hexdigest()==p['evidence']['sha256'],'evidence drift'; claims=active_claims([json.loads(l) for l in Path(p['claims']).read_text().splitlines() if l.strip()]); provider_claims=[x for x in claims if '1072' in json.dumps(x)]
heads={name:subprocess.check_output(['git','-C',root,'rev-parse','HEAD'],text=True).strip() for name,root in p['repositories'].items()}; drift={name:head for name,head in heads.items() if head!=p['expected_heads'][name]}
print(json.dumps({'tasks':rows,'claims1072':provider_claims,'heads':heads,'drift':drift,'next_authorized_action':'documentation and bounded readonly verification; no functional TASK admitted','limit':'fresh process reads checkpoint, not live independent-agent E2E; no transcript input or store writes'},ensure_ascii=False))
