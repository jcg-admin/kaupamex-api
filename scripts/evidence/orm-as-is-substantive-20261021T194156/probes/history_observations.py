"""Procedencia GitHub de los commits ya vinculados; sólo lectura."""
import concurrent.futures
import json
import subprocess
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'outputs'
v=json.loads((out/'task-assessments.json').read_text())
commits=set()
for task in v['tasks']:
    commits.update(c['sha'] for c in task['task_mentioned_commits'])
    commits.update(c['sha'] for c in task['commits_explicit_in_native_description'])
    commits.update(s['last_matching_line_change_commit'] for s in task['source_evidence'] if s.get('last_matching_line_change_commit'))
    commits.update(s['head_body_last_change_commit'] for s in task['source_evidence'] if s.get('head_body_last_change_commit'))
def observe(sha):
    observations={}
    for suffix in ('pulls','check-runs'):
        command=['gh','api',f'repos/jcg-admin/kaupamex-api/commits/{sha}/{suffix}']
        result=subprocess.run(command,text=True,capture_output=True,timeout=45)
        row={'command':command,'exit_code':result.returncode}
        if result.returncode==0:
            value=json.loads(result.stdout)
            if suffix=='pulls':
                row['results']=[{k:p.get(k) for k in ('number','state','merged_at','merge_commit_sha','html_url','title')} for p in value]
            else:
                row['results']=[{k:c.get(k) for k in ('name','head_sha','status','conclusion','details_url','completed_at')} for c in value['check_runs']]
                row['total_count']=value['total_count']
        else:row['error']=result.stderr[-1200:]
        observations[suffix]=row
    return sha,observations
rows=json.loads((out/'github-history.json').read_text())['commits'] if (out/'github-history.json').exists() else {}
missing=commits-set(rows)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for sha,observations in pool.map(observe,sorted(missing)):
        rows[sha]=observations
(out/'github-history.json').write_text(json.dumps({'repository':'jcg-admin/kaupamex-api','commits':rows,'interpretation':'Commit→PR association is not TASK acceptance; empty check list means no retained check-run evidence returned, not a PASS. Ancestry separately fixed to observed develop.'},indent=2)+'\n')
print('Scoped commits observed',len(rows),'failed API observations',sum(o['exit_code']!=0 for r in rows.values() for o in r.values()))
