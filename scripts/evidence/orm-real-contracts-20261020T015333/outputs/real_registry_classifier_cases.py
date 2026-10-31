"""Sonda temporal Consumer: contratos sin DB; no coordina TASK ni ejecución."""
import json,inspect,ast,pathlib,subprocess,os
import secrets
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.testing'
os.environ['SECRET_KEY']=secrets.token_urlsafe(40)
for prefix in ('DB_','DB_QA_'):
 for key,value in {'NAME':'kaupamex_audit_only','USER':'audit_only','PASSWORD':secrets.token_urlsafe(40),'HOST':'127.0.0.1','PORT':'65432','SSL_MODE':'disable','SOCKET':''}.items():os.environ[prefix+key]=value
from django.db.backends.base.base import BaseDatabaseWrapper
attempts=[]
def refuse_connection(self):
 attempts.append(self.alias)
 raise AssertionError('Esta sonda no autoriza acceso a DB')
BaseDatabaseWrapper.ensure_connection=refuse_connection
from django.conf import settings
import django
from django.db import models,connection
pristine=set(vars(models.Model))
django.setup()
import orm.models
import importlib.util,sys
from django.db import models
from django.apps import apps
from orm import registry
from types import SimpleNamespace
from collections import defaultdict
root=pathlib.Path.cwd()/'scripts/workbench'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
f=load('real_field_classifier',root/'registry-field-axis-support-20260903T053330/classify_field_axis_support.py')
s=load('real_signal_classifier',root/'registry-signaling-axis-support-20260903T063526/classify_signaling_axis_support.py')
rows=[]
for module in [f,s]:
 for sym in module.SYMBOLS:
  verdict=module.classify(sym)
  rows.append({'instrument':module.__name__,'name':sym.name,'installed':list(sym.installed),'primitives':list(sym.primitives),'classification':getattr(verdict,'kind',None) or getattr(verdict,'bucket',None),'both_lists_empty':not sym.installed and not sym.primitives,'installed_resolved':[bool(module.resolve(x)) if module is f else module.resolve(x) is not None for x in sym.installed],'implementation_in_current_registry':hasattr(registry.Registry,sym.name) or hasattr(registry,sym.name)})
assert not any(row['both_lists_empty'] for row in rows)
class NoDependentRelation(models.Model):
 _name='audit.no.dependent.relation'
 owner=models.ForeignKey(apps.get_model('base','ResPartner'),on_delete=models.DO_NOTHING,related_name='+',null=True)
 class Meta:app_label='base';managed=False
field=NoDependentRelation._meta.get_field('owner')
actual=registry.is_modifying_relations(field)
assert field.is_relation is True and actual is False
# El cuerpo real de Odoo sobre el mismo campo y la rama sin dependientes.
sys.path.insert(0,'scripts');import reference_roots as R
old=load('old_body_extractor',root/'basemodel-trae-contracts-20260911T050421/probes/extract_both_sides.py')
body=old.bodies(pathlib.Path(R.tree('odoo19c'))/'odoo/orm/registry.py',{'Registry'})['Registry']['is_modifying_relations'][0][2]
import textwrap
namespace={};exec(textwrap.dedent(body).replace('field: Field','field'),namespace)
ref=namespace['is_modifying_relations'](SimpleNamespace(_is_modifying_relations={},_field_triggers={},field_inverses=defaultdict(tuple)),field)
assert ref is False
result={'symbols':rows,'catalog_rows_both_declarations_empty':False,'real_fk_counterexample':{'django_is_relation':field.is_relation,'consumer_is_modifying_relations':actual,'reference_empty_dependency_branch':ref,'historical_classification':next(x['classification'] for x in rows if x['name']=='is_modifying_relations')},'field_inventory_entries':len(f.INVENTORY),'signal_inventory_entries':len(s.INVENTORY),'raw_shared_keys':len(set(f.INVENTORY)&set(s.INVENTORY)),'connection_attempts':attempts,'reference_scope':'exact method body, empty dependency branch; not full Odoo runtime'}
assert attempts==[]
print(json.dumps(result,ensure_ascii=False,indent=2))
pathlib.Path('/workspace/scratch/orm-real-contracts/real-classifier-cases.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
