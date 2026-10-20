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

import runpy,traceback
from pathlib import Path
results=[]
for rel in ["recoleccion-de-definiciones-20260911T175852/probe_the_override_loses_the_base.py", "fusion-de-declaraciones-de-campo-20260911T122051/probe_tree_redeclarations.py"]:
 print("\n=== EXISTING INSTRUMENT",rel,flush=True)
 try:
  mod=runpy.run_path(str(Path('scripts/workbench')/rel)); code=mod['main']();results.append({'instrument':rel,'exit_code':code})
 except Exception as e:
  traceback.print_exc();results.append({'instrument':rel,'blocked':type(e).__name__,'message':str(e)})
print('\nCONNECTION_ATTEMPTS',attempts)
print(json.dumps(results,indent=2))
assert not attempts
Path('/workspace/scratch/six-homes-review/override-current.json').write_text(json.dumps(results,indent=2)+'\n')
