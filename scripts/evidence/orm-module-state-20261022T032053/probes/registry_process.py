"""Verifica si el registro Django existente compone un roster en un proceso fresco."""
import json
import os
import sys
import traceback
from pathlib import Path

import django
from django.apps import apps
from django.core.checks import run_checks, Tags
from django.conf import settings

run = Path(__file__).resolve().parent.parent
result = {'requested_roster': os.environ['ORM_PROBE_MODULES'].split(','),
          'method': 'Fresh process, existing Django Apps; no per-request mutation or second registry'}
try:
    django.setup()
    result['effective_roster'] = sorted(settings.PROBE_MODULES)
    issues = run_checks(tags=[Tags.models])
    result['model_checks'] = [{'id': issue.id, 'message': issue.msg, 'object': str(issue.obj)} for issue in issues]
    result['model_checks_pass'] = not any(issue.level >= 40 for issue in issues)
    partner = apps.get_model('base', 'ResPartner')
    result['partner_city_id_available'] = hasattr(partner, 'city_id')
    result.update(status='PASS' if result['model_checks_pass'] else 'FAIL', apps=sorted(c.label for c in apps.get_app_configs()),
                  models=sorted(m._meta.label for m in apps.get_models()))
except Exception as error:
    result.update(status='FAIL', exception=type(error).__name__, message=str(error),
                  traceback=traceback.format_exc())
    traceback.print_exc()
finally:
    name = '-'.join(result['requested_roster'])
    if os.environ.get('ORM_PROBE_RESOLVE_DEPENDENCIES') == '1':
        name += '-autoclosure'
    (run/'outputs'/f'registry-process-{name}.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
sys.exit(0 if result['status']=='PASS' else 1)
