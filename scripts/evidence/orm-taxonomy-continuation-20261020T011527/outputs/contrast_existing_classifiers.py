"""Contraste aislado de dos instrumentos existentes; no define otra taxonomía."""
import importlib.util,sys,json,types
from pathlib import Path
from unittest.mock import patch
root=Path.cwd()/'scripts/workbench'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
f=load('audit_existing_field',root/'registry-field-axis-support-20260903T053330/classify_field_axis_support.py')
s=load('audit_existing_signaling',root/'registry-signaling-axis-support-20260903T063526/classify_signaling_axis_support.py')
rows=[]
for installed,primitives,present in [(('installed',),('primitive',),{'installed'}),((),(),set()),((),('primitive',),{'primitive'})]:
 fs=f.Symbol('fixture','fixture','fixture',('cpython','contencion por bytecode'),installed,primitives)
 ss=s.Symbol('fixture','fixture',list(installed),list(primitives),('cpython','contención por bytecode'))
 with patch.object(f,'resolve',lambda path:path in present),patch.object(s,'resolve',lambda path:object() if path in present else None):
  rows.append({'installed':installed,'primitives':primitives,'available':sorted(present),'field':f.classify(fs).kind,'signaling':s.classify(ss).bucket})
assert rows[0]['field']=='BLOCKED' and rows[0]['signaling']=='READY'
assert rows[1]['field']==rows[1]['signaling']=='BUILDABLE'
fixture=types.ModuleType('audit_classifier_fixture');fixture.none=None
sys.modules[fixture.__name__]=fixture
none_resolves={'field':f.resolve('audit_classifier_fixture.none'),'signaling_is_none':s.resolve('audit_classifier_fixture.none') is None}
assert none_resolves=={'field':True,'signaling_is_none':True}
def unsupported():raise NotImplementedError('negative behavior witness')
fixture.unsupported=unsupported
fs=f.Symbol('fixture','fixture','fixture',('cpython','contencion por bytecode'),('audit_classifier_fixture.unsupported',),())
ss=s.Symbol('fixture','fixture',['audit_classifier_fixture.unsupported'],[],('cpython','contención por bytecode'))
assert f.classify(fs).kind==s.classify(ss).bucket=='READY'
try:unsupported()
except NotImplementedError:behavior_failure=True
else:behavior_failure=False
assert behavior_failure
result={'cases':rows,'present_but_none':none_resolves,'unsupported_callable_classified_ready':True,'unsupported_callable_raises':behavior_failure,'inventory_field_entries':len(f.INVENTORY),'inventory_signaling_entries':len(s.INVENTORY),'raw_inventory_only_field':[list(x) for x in sorted(set(f.INVENTORY)-set(s.INVENTORY))],'raw_inventory_only_signaling':[list(x) for x in sorted(set(s.INVENTORY)-set(f.INVENTORY))]}
print(json.dumps(result,ensure_ascii=False,indent=2))
Path('/workspace/scratch/orm-taxonomy-continuation/classifier-contrast.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
