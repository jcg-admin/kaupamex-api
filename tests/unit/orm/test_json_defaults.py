"""TASK-API-0420: default literal fiel, aislado y serializable.

La infraestructura PostgreSQL y los fixtures de addons siguen perteneciendo
al Consumer. Estos casos no consideran aceptado el ORM por pasar checks.
"""
import unittest

from django.db import models
from django.db.migrations.writer import MigrationWriter
from django.utils.module_loading import import_string

from orm.fields_misc import Json


class JsonDefaultModel(models.Model):
    history = Json('History', default={'delete_messages': []})

    class Meta:
        app_label = 'json_default_contract'
        managed = False


class JsonDefaultTests(unittest.TestCase):
    def test_models_have_independent_nested_defaults(self):
        first, second = JsonDefaultModel(), JsonDefaultModel()
        self.assertEqual(first.history, {'delete_messages': []})
        self.assertIsNot(first.history, second.history)
        self.assertIsNot(first.history['delete_messages'], second.history['delete_messages'])
        first.history['delete_messages'].append('first')
        self.assertEqual(second.history, {'delete_messages': []})
        self.assertEqual(JsonDefaultModel().history, {'delete_messages': []})

    def test_default_checks_and_model_checks(self):
        field = JsonDefaultModel._meta.get_field('history')
        self.assertEqual(field.check(), [])
        self.assertEqual(JsonDefaultModel.check(), [])

    def test_migration_serialization_recreates_isolated_default(self):
        field = Json(default={'delete_messages': []})
        serialized, imports = MigrationWriter.serialize(field)
        namespace = {}
        for statement in imports:
            exec(statement, namespace)
        restored = eval(serialized, namespace)
        first, second = restored.get_default(), restored.get_default()
        first['delete_messages'].append('changed')
        self.assertEqual(second, {'delete_messages': []})
        self.assertEqual(restored.check(), [])

    def test_deconstruct_and_clone_preserve_content(self):
        original = Json(default={'delete_messages': []})
        _, path, args, kwargs = original.deconstruct()
        for field in (import_string(path)(*args, **kwargs), original.clone()):
            self.assertEqual(field.get_default(), {'delete_messages': []})
            self.assertIsNot(field.get_default(), field.get_default())

    def test_callable_none_missing_and_scalars(self):
        self.assertIs(Json(default=dict).default, dict)
        self.assertIsNone(Json(default=None, null=True).get_default())
        self.assertFalse(Json().has_default())
        for value in (False, 0, '', 2, 'value', [], [1, {'nested': []}]):
            with self.subTest(value=value):
                field = Json(default=value)
                self.assertEqual(field.get_default(), value)
                self.assertEqual(field._check_default(), [])

    def test_raw_django_negative_control(self):
        field = models.JSONField(default={'delete_messages': []})
        self.assertIs(field.get_default(), field.get_default())
        self.assertEqual([error.id for error in field._check_default()], ['fields.E010'])

    def test_related_and_store_metadata_are_preserved(self):
        for stored in (False, True):
            with self.subTest(store=stored):
                field = Json(related='parent.history', store=stored,
                             default={'delete_messages': []})
                self.assertEqual(field.related, 'parent.history')
                self.assertEqual(field.store, stored)
                self.assertEqual(field.get_default(), {'delete_messages': []})
                self.assertIsNot(field.get_default(), field.get_default())
