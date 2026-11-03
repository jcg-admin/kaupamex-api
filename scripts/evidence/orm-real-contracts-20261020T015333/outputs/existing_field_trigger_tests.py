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

import pytest
result=pytest.main(['-q','-c','/dev/null','--confcutdir=tests/unit/orm','tests/unit/orm/test_field_triggers.py'])
print('DB_CONNECTION_ATTEMPTS',attempts)
assert not attempts
raise SystemExit(result)
