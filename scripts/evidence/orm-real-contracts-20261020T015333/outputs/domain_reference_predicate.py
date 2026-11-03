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
import sys,ast,contextlib
sys.path.insert(0,'scripts')
import reference_roots as R
import orm.domains as consumer
from orm.environments import sudo,is_su
from django.apps import apps
from types import SimpleNamespace
from unittest.mock import patch
model=apps.get_model('base','ResGroups');field=model._meta.get_field('privilege')
ref_path=pathlib.Path(R.tree('odoo19c'))/'odoo/orm/domains.py'
tree=ast.parse(ref_path.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_optimize_any_with_rights');node.decorator_list=[]
namespace={'DomainCondition':consumer.DomainCondition};exec(compile(ast.Module(body=[node],type_ignores=[]),str(ref_path),'exec'),namespace)
reference=namespace['_optimize_any_with_rights'];original=field.bypass_search_access
rows=[]
try:
 assert is_su() is False
 for operator in ['any','not any']:
  for elevated,bypass in [(False,False),(True,False),(False,True),(True,True)]:
   field.bypass_search_access=bypass
   condition=consumer.Domain('privilege',operator,consumer.Domain('name','=','x'))
   # Protocolo exacto consumido por la función de referencia; campo real del Consumer.
   proxy=SimpleNamespace(env=SimpleNamespace(su=elevated))
   ref_condition=SimpleNamespace(field_expr=condition.field_expr,operator=condition.operator,value=condition.value,_field=lambda _:field)
   with sudo() if elevated else contextlib.nullcontext():actual=consumer._optimize_any_with_rights(condition,model)
   expected=reference(ref_condition,proxy)
   assert actual.operator==expected.operator
   if not elevated and not bypass:assert actual is condition and expected is ref_condition
   rows.append({'operator':operator,'elevated':elevated,'field_bypass':bypass,'reference_operator':expected.operator,'consumer_operator':actual.operator})
 field.bypass_search_access=False
 condition=consumer.Domain('privilege','any',consumer.Domain('name','=','x'))
 with sudo(),patch.object(consumer,'is_su',lambda:False):mutant=consumer._optimize_any_with_rights(condition,model)
 assert mutant.operator=='any' # El contrato bajo elevación exigiría any!.
 field.bypass_search_access=True
 with patch.object(field,'bypass_search_access',False):mutant2=consumer._optimize_any_with_rights(condition,model)
 assert mutant2.operator=='any'
 result={'reference':{'revision':'abe4040ec1a45beee90fb694e4eae4453e46b389','symbol':'odoo/orm/domains.py::_optimize_any_with_rights','lines':[node.lineno,node.end_lineno]},'cases':rows,'negative_controls_detect_elevation_and_field_bypass':True,'connection_attempts':attempts,'scope':'operator rewrite predicate only; not row access enforcement, generated SQL, nested domains or full Odoo runtime'}
 assert attempts==[]
 print(json.dumps(result,indent=2))
 pathlib.Path('/workspace/scratch/orm-real-contracts/domain-reference-predicate.json').write_text(json.dumps(result,indent=2)+'\n')
finally:field.bypass_search_access=original
