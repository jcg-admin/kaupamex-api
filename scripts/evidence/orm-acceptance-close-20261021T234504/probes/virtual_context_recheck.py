"""Repite exactamente el Consumer sin pk que antes retenía la etiqueta incorrecta."""
import json
import django
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext

django.setup()
from orm.environments import context_scope,transaction_scope

with CaptureQueriesContext(connection) as queries, transaction_scope():
    record=apps.get_model('base','ResGroups')(name='Operations')
    record.privilege=apps.get_model('base','ResGroupsPrivilege')(pk=43,name='Admin')
    first=record.full_name
    with context_scope(short_display_name=True):
        short=record.full_name
    restored=record.full_name
    assert (first,short,restored)==('Admin / Operations','Operations','Admin / Operations')
    assert record.pk is None
print(json.dumps({'first':first,'short':short,'restored':restored,'pk_still_none':True,
                  'queries':len(queries),'outcome':'PASS'}))
connection.close()
