"""Pruebas existentes del Consumer para contratos sin fixtures de persistencia."""
import json
import sys
from pathlib import Path
import django
import pytest

django.setup()
out=Path(__file__).resolve().parents[1]/'outputs'
label='incremental' if '--incremental' in sys.argv else 'scoped'
class Observations:
    def __init__(self):
        self.rows=[]
    def pytest_runtest_logreport(self,report):
        self.rows.append({'nodeid':report.nodeid,'phase':report.when,'outcome':report.outcome,'duration':report.duration})
    def pytest_sessionfinish(self,session,exitstatus):
        (out/(label+'-test-results.json')).write_text(json.dumps({'exit_code':int(exitstatus),'rows':self.rows},indent=2)+'\n')

names=['test_base_model_recordset','test_sorted_order_to_function','test_field_type_vocabulary',
 'test_comodel_name_contract','test_domain_optimizer_registry','test_domain_operator_optimizers',
 'test_domain_type_optimizers','test_field_cache','test_environments_transaction',
 'test_related_field_setup','test_field_triggers','test_field_resolve_depends','test_fields_html']
if '--incremental' in sys.argv:
    names=['test_nonstored_compute_dispatch','test_many2one_ondelete','test_field_definition_collection']
args=['--confcutdir=tests/unit/orm','-o','addopts=','--tb=short','-q',*[f'tests/unit/orm/{n}.py' for n in names]]
(out/(label+'-test-selection.json')).write_text(json.dumps({'files':names,'reason':'Explicit contract-unit selection, no mark filtering or omitted failures; DB fixture suites are separate gaps, not counted as passed.'},indent=2)+'\n')
raise SystemExit(pytest.main(args,plugins=[Observations()]))
