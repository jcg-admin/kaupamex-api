"""Contrato observable del Consumer ResGroups; no escribe ni consulta datos."""
import json
from pathlib import Path
import django
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext

django.setup()
model=apps.get_model('base','ResGroups')
record=model(name='ORM contract group')
result={'consumer':'base.ResGroups.full_name','expected':'ORM contract group','implementation_method_returns':record._compute_full_name()}
with CaptureQueriesContext(connection) as queries:
    try:
        result['actual']=record.full_name
        result['outcome']='PASS' if result['actual']==result['expected'] else 'CONTRACT_DIVERGENCE'
    except Exception as error:
        result['outcome']='CONTRACT_DIVERGENCE';result['exception']=type(error).__name__;result['message']=str(error)
result['query_count']=len(queries)
(Path(__file__).resolve().parents[1]/'outputs/nonstored-consumer.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['outcome']=='PASS' else 1)
