import sys,json,runpy
from pathlib import Path
blocked=[]
def deny_docs(event,args):
 if event=='open' and args and 'kaupamex-docs' in str(args[0]):
  blocked.append(str(args[0])); raise PermissionError('Docs forbidden in this bounded import control')
sys.addaudithook(deny_docs)
import django,rest_framework
runpy.run_path('/workspace/kaupamex-api/scripts/reference_roots.py',run_name='reference_boundary')
runpy.run_path('/workspace/kaupamex-api/src/orm/identifiers.py',run_name='identifier_boundary')
try: Path('/workspace/kaupamex-docs/AGENTS.md').read_text()
except PermissionError: pass
else: raise AssertionError('guard did not reject Docs read')
assert len(blocked)==1
print(json.dumps({'django':django.get_version(),'drf':rest_framework.VERSION,'bounded_api_imports_without_docs_open':'PASS','negative_guard':'PASS','limit':'Python open audit hook only; not OS sandbox/stat/access proof, fresh installation, API startup, ORM conformance or PostgreSQL test suite'}))
