"""Sonda discriminante de TASK-API-0420; no modifica ORM ni TaskStore.

Ejecutar desde API con PYTHONPATH=src, uv run --frozen python <este archivo>.
Usa el despachador real. No carga el conftest global ni acredita aceptación
de addons, PostgreSQL o ejecución de Odoo nativo.
"""
import json
import sys
import unittest
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.migrations.writer import MigrationWriter

from orm.fields_misc import Json


settings.configure(INSTALLED_APPS=[], DEFAULT_AUTO_FIELD='django.db.models.AutoField')
# No se registra un modelo ni se abre una base: se caracteriza el Field real.


class JsonDefaultContract(unittest.TestCase):
    def test_nested_defaults_are_independent(self):
        literal = {'delete_messages': []}
        field = Json('History', default=literal)
        first, second = field.get_default(), field.get_default()
        first['delete_messages'].append('only-first')
        self.assertEqual(second, {'delete_messages': []})
        self.assertEqual(literal, {'delete_messages': []})

    def test_literal_default_has_no_e010(self):
        field = Json('History', default={'delete_messages': []})
        self.assertEqual([e.id for e in field._check_default()], [])

    def test_callable_default_is_preserved(self):
        field = Json(default=dict)
        self.assertIs(field.default, dict)
        self.assertIsNot(field.get_default(), field.get_default())

    def test_none_default_is_preserved(self):
        field = Json(default=None, null=True)
        self.assertIsNone(field.get_default())
        self.assertEqual(field._check_default(), [])

    def test_absent_default_is_not_invented(self):
        field = Json()
        self.assertFalse(field.has_default())

    def test_literal_content_survives_deconstruction(self):
        field = Json('History', default={'delete_messages': []})
        _, path, args, kwargs = field.deconstruct()
        self.assertEqual(path, 'django.db.models.JSONField')
        serialized, imports = MigrationWriter.serialize(field)
        self.assertIn('delete_messages', serialized)
        clone = models.JSONField(*args, **kwargs)
        self.assertEqual(clone.get_default(), {'delete_messages': []})

    def test_negative_control_raw_django_shares_literal(self):
        field = models.JSONField(default={'delete_messages': []})
        self.assertIs(field.get_default(), field.get_default())
        self.assertIn('fields.E010', [e.id for e in field._check_default()])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(JsonDefaultContract)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        'task': 'TASK-API-0420',
        'tests_run': result.testsRun,
        'failures': [str(t) for t, _ in result.failures],
        'errors': [str(t) for t, _ in result.errors],
        'exit_code': 0 if result.wasSuccessful() else 1,
        'classification': 'BASELINE_FAILURE' if result.failures else 'not_verified',
        'limits': 'Field-only; no Odoo runtime, DB or addon acceptance',
    }
    destination = Path(__file__).resolve().parents[1] / 'outputs' / 'json-default-results.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    sys.exit(report['exit_code'])
