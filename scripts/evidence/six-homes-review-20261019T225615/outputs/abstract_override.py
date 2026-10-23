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


from django.db import models
from orm.fields import _collect_field_definitions
class AbstractParent(models.Model):
 label=models.CharField(max_length=9,compute='_compute_label')
 class Meta:
  abstract=True;app_label='audit_abstract'
class Child(AbstractParent):
 label=models.CharField(max_length=32,inverse='_inverse_label')
 class Meta:
  managed=False;app_label='audit_abstract'
p=AbstractParent._meta.get_field('label'); c=Child._meta.get_field('label')
result={'abstract_override_constructed':True,'parent_compute':p.compute,'child_compute':c.compute,'child_inverse':c.inverse,'child_max_length':c.max_length,'collected_links':len(_collect_field_definitions(c,Child,'label')),'connection_attempts':attempts}
assert p.compute=='_compute_label' and c.compute is None and c.inverse=='_inverse_label' and c.max_length==32
assert not attempts
print(json.dumps(result,indent=2))
pathlib.Path('/workspace/scratch/six-homes-review/abstract-override.json').write_text(json.dumps(result,indent=2)+'\n')
