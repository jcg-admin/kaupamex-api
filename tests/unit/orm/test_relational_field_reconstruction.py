"""TASK-API-0419: reconstrucción relacional por el protocolo público Django."""
import unittest
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.db import models
from django.test.utils import isolate_apps

from orm.fields import _merge_field_definitions
import orm.fields


class RelationalFieldReconstructionTests(unittest.TestCase):
    def test_foreign_key_preserves_target_policy_and_fresh_relation(self):
        base = models.ForeignKey('contenttypes.ContentType', models.CASCADE,
                                 verbose_name='Base', null=True)
        leaf = models.ForeignKey('contenttypes.ContentType', models.PROTECT,
                                 verbose_name='Leaf', null=False)
        merged = _merge_field_definitions((base, leaf))
        self.assertEqual(merged.remote_field.model.lower(), 'contenttypes.contenttype')
        self.assertIs(merged.remote_field.on_delete, models.PROTECT)
        self.assertIsNot(merged.remote_field, leaf.remote_field)
        self.assertIs(merged.remote_field.field, merged)
        self.assertIs(leaf.remote_field.field, leaf)
        self.assertFalse(merged.null)
        self.assertEqual(merged.verbose_name, 'Leaf')

    def test_last_foreign_key_target_wins(self):
        base = models.ForeignKey('contenttypes.OldTarget', models.CASCADE)
        leaf = models.ForeignKey('contenttypes.NewTarget', models.SET_NULL, null=True)
        merged = _merge_field_definitions((base, leaf))
        self.assertEqual(merged.remote_field.model.lower(), 'contenttypes.newtarget')
        self.assertIs(merged.remote_field.on_delete, models.SET_NULL)

    def test_many_to_many_preserves_constructor_arguments(self):
        base = models.ManyToManyField('contenttypes.ContentType', related_name='base')
        leaf = models.ManyToManyField('contenttypes.ContentType', related_name='leaf',
                                     db_table='contract_relations')
        merged = _merge_field_definitions((base, leaf))
        self.assertEqual(merged.remote_field.model.lower(), 'contenttypes.contenttype')
        self.assertEqual(merged.remote_field.related_name, 'leaf')
        self.assertEqual(merged.db_table, 'contract_relations')
        self.assertIs(merged.remote_field.field, merged)

    def test_one_to_one_retains_uniqueness_and_deletion_policy(self):
        base = models.OneToOneField('contenttypes.ContentType', models.CASCADE)
        leaf = models.OneToOneField('contenttypes.ContentType', models.PROTECT)
        merged = _merge_field_definitions((base, leaf))
        self.assertTrue(merged.unique)
        self.assertIs(merged.remote_field.on_delete, models.PROTECT)
        self.assertIs(merged.remote_field.field, merged)

    def test_scalar_declared_overrides_remain_intact(self):
        base = models.CharField(max_length=30, null=True, readonly=True)
        leaf = models.CharField(max_length=60, null=False)
        merged = _merge_field_definitions((base, leaf))
        self.assertEqual(merged.max_length, 60)
        self.assertFalse(merged.null)
        self.assertTrue(merged._args__['readonly'])
        self.assertEqual(merged._args__['_base_fields__'], (base, leaf))

    @isolate_apps()
    def test_real_model_mro_is_reachable_before_nonstored_removal(self):
        class Parent(models.Model):
            class Meta:
                app_label = 'contenttypes'

        class PlainMixin:
            parent = models.ForeignKey(Parent, models.CASCADE, related_name='+')

        class Child(PlainMixin, models.Model):
            parent = models.ForeignKey(Parent, models.PROTECT, related_name='+',
                                       related_query_name='contract_children')

            class Meta:
                app_label = 'contenttypes'

        field = Child._meta.get_field('parent')
        self.assertIs(field.remote_field.model, Parent)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertIs(field.remote_field.field, field)
        self.assertEqual(len(field._base_fields__), 2)
        self.assertEqual(field.related_query_name(), 'contract_children')
        self.assertEqual(field._args__['related_query_name'], 'contract_children')

    def test_django_native_clone_is_positive_control(self):
        field = models.ForeignKey('contenttypes.ContentType', models.PROTECT)
        clone = field.clone()
        self.assertEqual(clone.remote_field.model.lower(), 'contenttypes.contenttype')
        self.assertIs(clone.remote_field.on_delete, models.PROTECT)

    def test_reconstruction_during_django_application_startup(self):
        with tempfile.TemporaryDirectory(prefix='relational-startup-') as temporary:
            app = Path(temporary) / 'contract_app'
            app.mkdir()
            (app / '__init__.py').write_text('')
            (app / 'models.py').write_text('''import ast
import os
import subprocess
from pathlib import Path
import orm.models
import orm.fields
from django.db import models
if os.environ.get('ORM_RECONSTRUCTION_BASELINE') == '1':
    root = Path(orm.fields.__file__).resolve().parents[2]
    source = subprocess.check_output(['git','-C',str(root),'show',
        '79bc956e15f83c19714585246ba41501234a51fe:src/orm/fields.py'], text=True)
    for name in ('_merge_field_definitions','_m2m_contribute_to_class'):
        node = next(n for n in ast.parse(source).body
            if isinstance(n,ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<original>','exec'),
             orm.fields.__dict__)
    for field_type in (models.ForeignKey,models.ManyToManyField):
        if hasattr(field_type.__init__,'__wrapped__'):
            field_type.__init__ = field_type.__init__.__wrapped__
    models.ForeignKey.contribute_to_class = orm.fields._DJANGO_FK_CONTRIBUTE
    models.ManyToManyField.contribute_to_class = orm.fields._m2m_contribute_to_class
class Parent(models.Model):
    pass
class Mixin:
    parent = models.ForeignKey(Parent, models.CASCADE)
class Child(Mixin, models.Model):
    parent = models.ForeignKey(Parent, models.PROTECT)
''')
            env = dict(os.environ)
            env['PYTHONPATH'] = str(Path(orm.fields.__file__).resolve().parents[1])
            command = '''import django
from django.conf import settings
settings.configure(INSTALLED_APPS=['django.contrib.contenttypes','contract_app'], DEFAULT_AUTO_FIELD='django.db.models.AutoField')
django.setup()
from contract_app.models import Parent,Child
assert Child._meta.get_field('parent').remote_field.model is Parent
'''
            result = subprocess.run([sys.executable, '-c', command], cwd=temporary,
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
