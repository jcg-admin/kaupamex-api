"""Anula sólo la identidad privada de caché, sin modificar archivos ni pk."""
import sys
import django
import pytest

django.setup()
from orm import fields as field_module
from orm.identifiers import NewId

if '--shared-identity' in sys.argv:
    shared = NewId()
    field_module._field_cache_record_id = lambda field, instance: shared if instance.pk is None else instance.pk
    selected = ['test_unsaved_instances_have_separate_contextual_values']
else:
    field_module._field_cache_record_id = lambda field, instance: instance.pk
    selected = ['test_unsaved_context_switch_preserves_each_cached_value',
                'test_unsaved_instances_have_separate_contextual_values']
print('Negative control: cache identity only; pk and persistence untouched', flush=True)
raise SystemExit(pytest.main(['--confcutdir=tests/unit/orm','-o','addopts=','--tb=short','-q',
    *['tests/unit/orm/test_res_groups_compute_contract.py::'+name for name in selected]]))
