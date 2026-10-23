"""Regresión Consumer: defaults JSON, vocabulario y reconstrucción relacional."""
import importlib
import django
import pytest
from django.conf import settings
settings.configure(INSTALLED_APPS=['django.contrib.contenttypes'], DEFAULT_AUTO_FIELD='django.db.models.AutoField')
django.setup()
importlib.import_module('orm.models')
raise SystemExit(pytest.main(['--confcutdir=tests/unit/orm','-o','DJANGO_SETTINGS_MODULE=',
 '-o','addopts=','tests/unit/orm/test_field_required_declared.py',
 'tests/unit/orm/test_declared_source_vocabulary.py','tests/unit/orm/test_json_defaults.py',
 'tests/unit/orm/test_relational_field_reconstruction.py','-q']))
