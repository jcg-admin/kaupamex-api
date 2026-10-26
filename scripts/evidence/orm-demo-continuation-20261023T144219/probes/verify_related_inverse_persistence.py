"""Measure related scalar persistence without changing the Consumer contract."""
import json
import hashlib
from pathlib import Path
import sys
import subprocess

import django
from django.db import transaction
from django.test.utils import CaptureQueriesContext
from django.db import connection

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
django.setup()

from addons.base.models import ResBank, ResCountry, ResPartner, ResPartnerBank

before = (ResBank.objects.count(), ResPartnerBank.objects.count(), ResPartner.objects.count())
results = []
with transaction.atomic():
    country, _ = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'Mexico'})
    for source, destination, expected in [
        ('bank_name', 'name', 'Updated bank'), ('bank_bic', 'bic', 'FIXDMXMM'),
    ]:
        bank = ResBank.objects.create(name='Original bank', bic='ORIGMXMM', country=country)
        partner = ResPartner.objects.create(name='Related persistence probe')
        account = ResPartnerBank.objects.create(
            acc_number='01234567891' if source == 'bank_name' else '01234567892',
            bank=bank, partner=partner)
        field = account._meta.get_field(source)
        with CaptureQueriesContext(connection) as queries:
            setattr(account, source, expected)
        assert len(queries) == 0
        before_save = ResBank.objects.values_list(destination, flat=True).get(pk=bank.pk)
        account.save()
        cached_target = getattr(account.bank, destination)
        stored_target = ResBank.objects.values_list(destination, flat=True).get(pk=bank.pk)
        results.append({
            'source_field': source, 'target_field': destination,
            'compute': str(field.compute), 'inverse': str(field.inverse),
            'assignment_queries': len(queries), 'before_save': before_save,
            'target_cache_after_save': cached_target,
            'target_database_after_save': stored_target,
            'expected_database_after_save': expected,
            'persistent_contract_satisfied': stored_target == expected,
        })
    transaction.set_rollback(True)
after = (ResBank.objects.count(), ResPartnerBank.objects.count(), ResPartner.objects.count())
assert after == before
result = {
    'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'consumer_fields_sha256': hashlib.sha256((Path(__file__).resolve().parents[4] / 'src/orm/fields.py').read_bytes()).hexdigest(),
    'task': 'TASK-GEN-0633 historical related-write triage; TASK-API-0412 completed predecessor, not reopened',
    'cases': results, 'business_row_counts_unchanged': True,
    'scope': 'Diagnostic of two actual stored scalar targets via existing save; no state change or whole inverse-family acceptance',
}
output = Path(__file__).resolve().parents[1] / 'outputs/related-inverse-persistence-current.json'
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
assert all(case['persistent_contract_satisfied'] for case in results)
