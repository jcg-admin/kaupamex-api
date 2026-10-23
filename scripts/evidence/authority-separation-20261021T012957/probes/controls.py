import os,json,tempfile,argparse,subprocess,hashlib
from pathlib import Path
from unittest.mock import patch
from paths import reach
from workbench.paths import workbench_dir
from cache.paths import cache_dir
from session.job_runs import jobs_dir
from session.node_next_task import next_for_node
from verify.tree_fingerprint import fingerprint
out=Path('/workspace/scratch/authority-separation'); observations=[]
# Pure resolver controls: fixtures have no consumers or DB records in live storage.
with tempfile.TemporaryDirectory(prefix='independence-',dir=out) as temp:
 base=Path(temp); provider=base/'provider'; marker=provider/reach.THYROX_MARKER; marker.parent.mkdir(parents=True); marker.write_text('# isolated root marker, not executable Provider copy\n'); (provider/'.claude').mkdir(); empty=base/'empty.env'; empty.write_text('')
 override={'THYROX_ROOT':str(provider),'THYROX_ENV_FILE':str(empty),'THYROX_WORKBENCH_DIR':str(provider/'bench'),'THYROX_CACHE_DIR':str(provider/'cache'),'THYROX_JOBS_DIR':str(provider/'jobs')}
 with patch.dict(os.environ,override):
  # avoid accidental inherited consumer/store routing only for this in-process fixture.
  with patch.dict(os.environ,{'THYROX_CONSUMER':'','THYROX_AGENT_STORE':'','KAUPAMEX_AGENT_STORE':''}):
   values={'provider':str(reach.thyrox_root(provider)),'store':str(reach.agent_store_path(provider,create=False)),'workbench':str(workbench_dir(provider)),'jobs':str(jobs_dir(provider)),'cache':str(cache_dir(provider))}; assert all(str(provider) in v for v in values.values()); assert not (provider/'agent-results').exists(); observations.append({'control':'Provider roots without any Kaupamex checkout in fixture','result':'PASS','values':values,'limit':'Production modules imported from fixed Provider checkout; path/control independence only, not isolated installation or runtime E2E'})
 consumers=[]
 for name in ['alpha-service','warehouse-ledger']:
  p=base/name; (p/'.claude').mkdir(parents=True); (p/'.git').mkdir(); consumers.append(p)
 with patch.dict(os.environ,{**override,'THYROX_CONSUMER':'','THYROX_WORKBENCH_DIR':'bench','THYROX_CACHE_DIR':'cache','THYROX_JOBS_DIR':'jobs'}):
  resolved=[]
  for p in consumers:
   roots={'consumer':str(reach.consumer_root(start=p)),'workbench':str(workbench_dir(p)),'cache':str(cache_dir(p)),'jobs':str(jobs_dir(p))}; assert all(v.startswith(str(p)) for v in roots.values()),roots; resolved.append(roots)
  assert resolved[0]['workbench']!=resolved[1]['workbench']; observations.append({'control':'Arbitrary named and multiple Consumers','result':'PASS','values':resolved,'limit':'Explicit generic homes, empty fixture env file; does not prove ownership or operational multiwriter storage isolation'})
 # Negative control: a declared single consumer can capture another start in legacy mode.
 with patch.dict(os.environ,{**override,'THYROX_CONSUMER':str(consumers[0]),'THYROX_CONSUMER_STRICT':''}):
  got=reach.consumer_root(start=consumers[1]); assert got==consumers[0]; observations.append({'control':'Global consumer declaration with another start','result':'OBSERVED_CONFIGURATION_HAZARD','observed':str(got),'limit':'Legacy behavior by source contract; explicitly pass declared root/per-clone configuration and qualify strict mode, do not silently call independent'})
# Native graph fixture, not new scheduler or operational TASK.
graph=[{'id':'existing-predecessor','lane':'A','state':'accepted','owned':['src/a'],'dependsOn':[]},{'id':'existing-dependent','lane':'A','state':'queued','owned':['src/b'],'dependsOn':['existing-predecessor']}]
assert next_for_node(graph,[],'A')=='existing-dependent'
foreign=[{'op':'claim','owner':'vm-r','path':'src/b','task':'TASK-THYROX-1072'}]
assert next_for_node(graph,foreign,'A') is None
graph[0]['state']='queued'; graph[0]['lane']='B'; assert next_for_node(graph,[],'A') is None
observations.append({'control':'Native next_for_node accepted dependency / foreign claim / unresolved predecessor','result':'PASS','limit':'In-memory graph fixture only; does not adjudicate live task ownership or resource qualification'})
(out/'isolation-controls.json').write_text(json.dumps({'provider_revision':subprocess.check_output(['git','-C','/workspace/thyrox','rev-parse','HEAD'],text=True).strip(),'observations':observations,'no_models_or_real_store_writes':True},indent=2)+'\n')
print(json.dumps(observations,indent=2))
