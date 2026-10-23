"""TASK-API-0419: alcance persistente de la FK reconstruida, PostgreSQL TEMP."""
import unittest

import pytest
from django.db import IntegrityError, connection, models, transaction
from django.db.models.deletion import ProtectedError


class ContractParent(models.Model):
    label = models.CharField(max_length=30)

    class Meta:
        app_label = 'contenttypes'
        managed = False
        db_table = 'orm_relation_parent_contract'


class RelationMixin:
    parent = models.ForeignKey(ContractParent, models.CASCADE, related_name='+')


class ContractChild(RelationMixin, models.Model):
    parent = models.ForeignKey(ContractParent, models.PROTECT,
                               related_name='contract_children')

    class Meta:
        app_label = 'contenttypes'
        managed = False
        db_table = 'orm_relation_child_contract'


class ContractCascadeChild(RelationMixin, models.Model):
    parent = models.ForeignKey(ContractParent, models.CASCADE,
                               related_name='contract_cascade_children')

    class Meta:
        app_label = 'contenttypes'
        managed = False
        db_table = 'orm_relation_cascade_contract'


@pytest.mark.django_db(transaction=True)
class RelationalPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert connection.vendor == 'postgresql'
        with connection.schema_editor(collect_sql=True) as editor:
            for model in (ContractParent, ContractChild, ContractCascadeChild):
                editor.create_model(model)
        with connection.cursor() as cursor:
            for sql in editor.collected_sql:
                assert sql.startswith(('CREATE TABLE ', 'ALTER TABLE ', 'CREATE INDEX ')), sql
                cursor.execute(sql.replace('CREATE TABLE ', 'CREATE TEMP TABLE ', 1))

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            for table in ('orm_relation_child_contract', 'orm_relation_cascade_contract',
                          'orm_relation_parent_contract'):
                cursor.execute('DROP TABLE pg_temp.' + table)

    def setUp(self):
        with connection.cursor() as cursor:
            for table in ('orm_relation_child_contract', 'orm_relation_cascade_contract',
                          'orm_relation_parent_contract'):
                cursor.execute('DELETE FROM pg_temp.' + table)

    def test_forward_reverse_and_query_use_reconstructed_relation(self):
        parent = ContractParent.objects.create(label='Parent')
        child = ContractChild.objects.create(parent=parent)
        child.refresh_from_db()
        self.assertEqual(child.parent.pk, parent.pk)
        self.assertEqual(parent.contract_children.get().pk, child.pk)
        self.assertEqual(ContractChild.objects.get(parent__label='Parent').pk, child.pk)
        field = ContractChild._meta.get_field('parent')
        self.assertEqual(len(field._base_fields__), 2)
        self.assertIs(field.remote_field.field, field)

    def test_leaf_protect_policy_prevents_parent_deletion(self):
        parent = ContractParent.objects.create(label='Protected')
        child = ContractChild.objects.create(parent=parent)
        with self.assertRaises(ProtectedError):
            parent.delete()
        self.assertTrue(ContractParent.objects.filter(pk=parent.pk).exists())
        self.assertTrue(ContractChild.objects.filter(pk=child.pk).exists())

    def test_leaf_cascade_policy_deletes_only_dependent_child(self):
        parent = ContractParent.objects.create(label='Cascade')
        other = ContractParent.objects.create(label='Unrelated')
        child = ContractCascadeChild.objects.create(parent=parent)
        child_id = child.pk
        parent.delete()
        self.assertFalse(ContractCascadeChild.objects.filter(pk=child_id).exists())
        self.assertTrue(ContractParent.objects.filter(pk=other.pk).exists())

    def test_postgresql_rejects_orphan_foreign_key(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('INSERT INTO pg_temp.orm_relation_child_contract (parent_id) VALUES (%s)', [987654321])
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertEqual(ContractChild.objects.count(), 0)

    def test_relation_update_obeys_rollback(self):
        original = ContractParent.objects.create(label='Original')
        replacement = ContractParent.objects.create(label='Replacement')
        child = ContractChild.objects.create(parent=original)
        with transaction.atomic():
            child.parent = replacement
            child.save(update_fields=['parent'])
            self.assertEqual(ContractChild.objects.get(pk=child.pk).parent_id, replacement.pk)
            transaction.set_rollback(True)
        child.refresh_from_db()
        self.assertEqual(child.parent_id, original.pk)
