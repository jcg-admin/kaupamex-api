"""TASK-GEN-0559: pendientes sin fila no deben perpetuar el recálculo.

Tablas TEMP sobre PostgreSQL; no migraciones ni datos de aplicaciones.
"""
import unittest
from unittest.mock import patch

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, models, transaction
from django.test.utils import CaptureQueriesContext

import api
import fields
from exceptions import AccessError, MissingError
from orm import registry
from orm.environments import env, transaction_scope
from orm.identifiers import NewId
from orm.models import _recompute_field, _flush


class MissingRecomputeModel(models.Model):
    _name = 'orm.missing.recompute'
    _description = 'Missing recompute contract'
    source = fields.Integer(default=0)
    doubled = fields.Integer(compute='_compute_pair', store=True, null=True)
    tripled = fields.Integer(compute='_compute_pair', store=True, null=True)
    untouched = fields.Integer(compute='_compute_untouched', store=True, null=True)

    class Meta:
        app_label = 'contenttypes'
        managed = False
        db_table = 'orm_missing_recompute_contract'

    @api.depends('source')
    def _compute_pair(self):
        self.doubled = self.source * 2
        self.tripled = self.source * 3

    @api.depends('source')
    def _compute_untouched(self):
        self.untouched = self.source


@pytest.mark.django_db(transaction=True)
class MissingRecomputeFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert connection.vendor == 'postgresql', 'PostgreSQL requerido'
        with connection.schema_editor(collect_sql=True) as editor:
            editor.create_model(MissingRecomputeModel)
        with connection.cursor() as cursor:
            for sql in editor.collected_sql:
                assert sql.startswith('CREATE TABLE '), sql
                cursor.execute(sql.replace('CREATE TABLE ', 'CREATE TEMP TABLE ', 1))

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE pg_temp.orm_missing_recompute_contract')

    def setUp(self):
        registry.clear_field_depends()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM pg_temp.orm_missing_recompute_contract')
        self.field = MissingRecomputeModel._meta.get_field('doubled')
        self.sibling = MissingRecomputeModel._meta.get_field('tripled')
        self.other = MissingRecomputeModel._meta.get_field('untouched')

    def tearDown(self):
        registry.clear_field_depends()

    def mark_pair(self, ids):
        for field in (self.field, self.sibling):
            env().add_to_compute(field, ids)


class MissingRecomputeTests(MissingRecomputeFixture):
    def test_all_missing_clears_computed_group_only(self):
        with transaction_scope():
            self.mark_pair([987654321])
            env().add_to_compute(self.other, [987654321])
            _recompute_field(MissingRecomputeModel, self.field)
            self.assertFalse(env().records_to_compute(self.field))
            self.assertFalse(env().records_to_compute(self.sibling))
            self.assertIn(987654321, env().records_to_compute(self.other))

    def test_mixed_rows_compute_flush_and_remove_deleted_pending(self):
        row = MissingRecomputeModel.objects.create(source=7)
        deleted = MissingRecomputeModel.objects.create(source=13)
        deleted_id = deleted.pk
        deleted.delete()
        with transaction_scope():
            self.mark_pair([row.pk, deleted_id])
            _recompute_field(MissingRecomputeModel, self.field)
            self.assertFalse(env().records_to_compute(self.field))
            self.assertFalse(env().records_to_compute(self.sibling))
            _flush(MissingRecomputeModel)
        row.refresh_from_db()
        self.assertEqual((row.doubled, row.tripled), (14, 21))
        self.assertFalse(MissingRecomputeModel.objects.filter(pk=deleted_id).exists())

    def test_requested_subset_keeps_other_pending_ids(self):
        with transaction_scope():
            self.mark_pair([987654321, 987654322])
            _recompute_field(MissingRecomputeModel, self.field, [987654321])
            self.assertEqual(set(env().records_to_compute(self.field)), {987654322})
            self.assertEqual(set(env().records_to_compute(self.sibling)), {987654322})

    def test_virtual_ids_are_not_missing_persisted_rows(self):
        virtual = NewId()
        with transaction_scope():
            self.mark_pair([virtual, None, 987654321])
            _recompute_field(MissingRecomputeModel, self.field)
            self.assertEqual(set(env().records_to_compute(self.field)), {virtual, None})

    def test_compute_failure_does_not_accept_missing_or_existing_work(self):
        row = MissingRecomputeModel.objects.create(source=7)
        with transaction_scope():
            self.mark_pair([row.pk, 987654321])
            with patch.object(MissingRecomputeModel, '_compute_pair', side_effect=ValueError('compute failed')):
                with self.assertRaisesRegex(ValueError, 'compute failed'):
                    _recompute_field(MissingRecomputeModel, self.field)
            self.assertEqual(set(env().records_to_compute(self.field)), {row.pk, 987654321})
            self.assertEqual(set(env().records_to_compute(self.sibling)), {row.pk, 987654321})

    def test_no_pending_avoids_database_queries(self):
        with transaction_scope(), CaptureQueriesContext(connection) as queries:
            _recompute_field(MissingRecomputeModel, self.field)
        self.assertEqual(len(queries), 0)

    def test_recomputed_column_update_obeys_postgresql_rollback(self):
        row = MissingRecomputeModel.objects.create(source=5)
        with connection.cursor() as cursor:
            cursor.execute('SELECT doubled FROM pg_temp.orm_missing_recompute_contract WHERE id=%s', [row.pk])
            initial = cursor.fetchone()[0]
        with transaction.atomic():
            with transaction_scope():
                self.mark_pair([row.pk])
                _recompute_field(MissingRecomputeModel, self.field)
                _flush(MissingRecomputeModel)
                with connection.cursor() as cursor:
                    cursor.execute('SELECT doubled FROM pg_temp.orm_missing_recompute_contract WHERE id=%s', [row.pk])
                    self.assertEqual(cursor.fetchone()[0], 10)
            transaction.set_rollback(True)
        with connection.cursor() as cursor:
            cursor.execute('SELECT doubled FROM pg_temp.orm_missing_recompute_contract WHERE id=%s', [row.pk])
            self.assertEqual(cursor.fetchone()[0], initial)


class MissingRecomputeRetryTests(MissingRecomputeFixture):
    """La desaparición durante el cálculo, distinta de faltar al consultar."""

    def test_retry_missing_error_discards_deleted_record(self):
        row = MissingRecomputeModel.objects.create(source=7)
        def disappear(record):
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM pg_temp.orm_missing_recompute_contract WHERE id=%s', [record.pk])
            raise MissingError('record deleted during compute')
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=disappear):
                self.field.recompute([row])
            self.assertFalse(env().records_to_compute(self.field))
            self.assertFalse(env().records_to_compute(self.sibling))

    def test_retry_django_missing_discards_deleted_record(self):
        row = MissingRecomputeModel.objects.create(source=7)
        def disappear(record):
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM pg_temp.orm_missing_recompute_contract WHERE id=%s', [record.pk])
            MissingRecomputeModel.objects.get(pk=record.pk)
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=disappear):
                self.field.recompute([row])
            self.assertFalse(env().records_to_compute(self.field))
            self.assertFalse(env().records_to_compute(self.sibling))

    def test_retry_existing_record_computes_once_after_missing_error(self):
        row = MissingRecomputeModel.objects.create(source=7)
        original = MissingRecomputeModel._compute_pair
        calls = []
        def transient(record):
            calls.append(record.pk)
            if len(calls) == 1:
                raise MissingError('transient missing read')
            original(record)
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=transient):
                self.field.recompute([row])
            self.assertEqual(calls, [row.pk, row.pk])
            self.assertFalse(env().records_to_compute(self.field))
            _flush(MissingRecomputeModel)
        row.refresh_from_db()
        self.assertEqual((row.doubled, row.tripled), (14, 21))

    def test_retry_repeated_missing_error_propagates_and_preserves_work(self):
        row = MissingRecomputeModel.objects.create(source=7)
        calls = []
        def missing(record):
            calls.append(record.pk)
            raise MissingError('still missing')
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=missing):
                with self.assertRaises(MissingError):
                    self.field.recompute([row])
            self.assertEqual(calls, [row.pk, row.pk])
            self.assertIn(row.pk, env().records_to_compute(self.field))
            self.assertIn(row.pk, env().records_to_compute(self.sibling))

    def test_retry_missing_related_object_keeps_primary_record_pending(self):
        row = MissingRecomputeModel.objects.create(source=7)
        calls = []
        def missing_related(record):
            calls.append(record.pk)
            raise ObjectDoesNotExist('related object still missing')
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=missing_related):
                with self.assertRaises(ObjectDoesNotExist):
                    self.field.recompute([row])
            self.assertEqual(calls, [row.pk, row.pk])
            self.assertTrue(MissingRecomputeModel.objects.filter(pk=row.pk).exists())
            self.assertIn(row.pk, env().records_to_compute(self.field))


    def test_retry_virtual_record_does_not_query_or_discard_it(self):
        row = MissingRecomputeModel(source=7)
        calls = []
        def missing(record):
            calls.append(record.pk)
            raise MissingError('virtual record')
        with transaction_scope():
            self.mark_pair([None])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=missing):
                with CaptureQueriesContext(connection) as queries:
                    with self.assertRaises(MissingError):
                        self.field.recompute([row])
            self.assertEqual(calls, [None, None])
            self.assertEqual(len(queries), 0)
            self.assertIn(None, env().records_to_compute(self.field))


    def test_retry_internal_existence_does_not_use_filtered_public_manager(self):
        row = MissingRecomputeModel.objects.create(source=7)
        original = MissingRecomputeModel._compute_pair
        calls = []
        def transient(record):
            calls.append(record.pk)
            if len(calls) == 1:
                raise MissingError('transient')
            original(record)
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=transient):
                with patch.object(MissingRecomputeModel.objects, 'filter', side_effect=AssertionError('public manager used')):
                    self.field.recompute([row])
            self.assertEqual(calls, [row.pk, row.pk])
            self.assertFalse(env().records_to_compute(self.field))

    def test_retry_does_not_catch_access_errors(self):
        row = MissingRecomputeModel.objects.create(source=7)
        calls = []
        def denied(record):
            calls.append(record.pk)
            raise AccessError('denied')
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=denied):
                with self.assertRaises(AccessError):
                    self.field.recompute([row])
            self.assertEqual(calls, [row.pk])
            self.assertIn(row.pk, env().records_to_compute(self.field))


    def test_retry_uses_record_database_instead_of_read_router(self):
        row = MissingRecomputeModel.objects.create(source=7)
        original = MissingRecomputeModel._compute_pair
        calls = []
        def transient(record):
            calls.append(record.pk)
            if len(calls) == 1:
                raise MissingError('transient')
            original(record)
        with transaction_scope():
            self.mark_pair([row.pk])
            with patch.object(MissingRecomputeModel, '_compute_pair', new=transient):
                with patch('django.db.router.db_for_read', return_value='not_configured_for_this_contract'):
                    self.field.recompute([row])
            self.assertEqual(calls, [row.pk, row.pk])
            self.assertFalse(env().records_to_compute(self.field))
