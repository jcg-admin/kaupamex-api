"""Sonda temporal Consumer: contratos sin DB; no coordina TASK ni ejecución."""
import json,inspect,ast,pathlib,subprocess,os
import secrets
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.testing'
os.environ['SECRET_KEY']=secrets.token_urlsafe(40)
profile={}
for line in pathlib.Path('/workspace/kaupamex-db/.env.example').read_text().splitlines():
 if '=' in line and not line.startswith('#'):
  key,value=line.split('=',1);profile[key]=value
for prefix in ('DB_','DB_QA_'):
 for key,value in {'NAME':profile['DB_QA_NAME'],'USER':profile['DB_QA_USER'],'PASSWORD':profile['DB_QA_PASSWORD'],'HOST':'127.0.0.1','PORT':'5432','SSL_MODE':'disable','SOCKET':''}.items():os.environ[prefix+key]=value
from django.db.backends.base.base import BaseDatabaseWrapper
original_connect=BaseDatabaseWrapper.ensure_connection
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
# El setup no puede consultar; sólo después se abre la conexión QA autorizada.
assert attempts==[]
BaseDatabaseWrapper.ensure_connection=original_connect
import orm.models
from orm.registry import Registry
from django.db import transaction, DatabaseError
import psycopg
from psycopg.pq import TransactionStatus

registry=object.__new__(Registry)
registry.db_name='default'
connection.ensure_connection()
assert connection.settings_dict['NAME']==profile['DB_QA_NAME']
observer=psycopg.connect(dbname=profile['DB_QA_NAME'],user=profile['DB_QA_USER'],password=profile['DB_QA_PASSWORD'],host='127.0.0.1',port=5432,autocommit=True,connect_timeout=5)
lock_id=secrets.randbelow(2**30)
rows=[]
def free():
 with observer.cursor() as cur:
  cur.execute('SELECT pg_try_advisory_xact_lock(%s)',(lock_id,))
  return cur.fetchone()[0]
def status():return connection.connection.info.transaction_status.name
try:
 assert free()
 connection.set_autocommit(False)
 with registry.cursor() as cur:
  cur.execute('SELECT pg_advisory_xact_lock(%s)',[lock_id])
 after=status();released=free()
 rows.append({'case':'Registry.cursor normal exit, autocommit=False','transaction_status':after,'lock_released':released})
 assert after=='INTRANS' and released is False
 connection.rollback();assert free()
 try:
  with registry.cursor() as cur:cur.execute('SELECT 1/0')
 except DatabaseError:
  after=status();rows.append({'case':'Registry.cursor SQL error exit','transaction_status':after});assert after=='INERROR'
 else:raise AssertionError('SQL error not observed')
 connection.rollback();connection.set_autocommit(True)
 with transaction.atomic():
  with connection.cursor() as cur:cur.execute('SELECT pg_advisory_xact_lock(%s)',[lock_id])
 rows.append({'case':'Django atomic normal exit','transaction_status':status(),'lock_released':free()})
 assert rows[-1]['transaction_status']=='IDLE' and rows[-1]['lock_released'] is True
 try:
  with transaction.atomic():
   with connection.cursor() as cur:
    cur.execute('SELECT pg_advisory_xact_lock(%s)',[lock_id])
    cur.execute('SELECT 1/0')
 except DatabaseError:pass
 else:raise AssertionError('SQL error not observed')
 rows.append({'case':'Django atomic SQL error exit','transaction_status':status(),'lock_released':free()})
 assert rows[-1]['transaction_status']=='IDLE' and rows[-1]['lock_released'] is True
 with observer.cursor() as cur:
  cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'");count=cur.fetchone()[0]
 assert count==0
 result={'database':profile['DB_QA_NAME'],'schema_tables_after':count,'setup_connection_attempts':attempts,'cases':rows,'uses_data_writes_or_ddl':False,'scope':'cursor transaction lifecycle only; no full Odoo runtime, pool, replica or hook equivalence'}
 print(json.dumps(result,indent=2))
 pathlib.Path('/workspace/scratch/orm-real-contracts/cursor-contract.json').write_text(json.dumps(result,indent=2)+'\n')
finally:
 if connection.connection is not None:
  connection.rollback();connection.close()
 observer.close()
