"""Class-declared virtual relations do not invent a physical delete edge.

These controls qualify Django metadata, dependency warnings and collection.
Actual PostgreSQL deletion is exercised by the companion Consumer probe.
"""

from django.db import models
from django.db.models.deletion import Collector
import pytest

import api
import fields
from orm import registry


class VirtualDeleteTarget(models.Model):
    _name = 'orm.virtual.delete.target'
    label = fields.Char(max_length=32)

    class Meta:
        app_label = 'contenttypes'
        managed = False


class VirtualDeleteSource(models.Model):
    _name = 'orm.virtual.delete.source'
    target = fields.Many2one(
        VirtualDeleteTarget,
        compute='_compute_target',
        inverse='_inverse_target',
        ondelete='set null',
        null=True,
        related_name='virtual_sources',
    )
    echo = fields.Char(compute='_compute_echo')

    class Meta:
        app_label = 'contenttypes'
        managed = False

    def _compute_target(self):
        self.target = None

    def _inverse_target(self):
        return None

    @api.depends('target.label')
    def _compute_echo(self):
        self.echo = self.target.label if self.target else ''


@pytest.fixture
def target_field():
    registry.clear_field_depends()
    yield VirtualDeleteSource._meta.get_field('target')
    registry.clear_field_depends()


def test_class_declared_virtual_relation_has_no_physical_column(target_field):
    assert target_field in VirtualDeleteSource._meta.private_fields
    assert target_field not in VirtualDeleteSource._meta.concrete_fields
    assert target_field.column is None
    assert target_field.store is False


def test_declared_policy_survives_without_a_django_delete_edge(target_field):
    assert target_field.ondelete == 'set null'
    assert target_field.remote_field.on_delete is models.DO_NOTHING


def test_native_collector_does_not_schedule_virtual_column_updates(
    target_field,
):
    collector = Collector(using='default')
    collector.collect([VirtualDeleteTarget(pk=31)])
    assert not collector.field_updates


def test_unsearchable_dependency_warning_keeps_the_contract_visible(
    target_field,
):
    echo = VirtualDeleteSource._meta.get_field('echo')
    with pytest.warns(UserWarning, match='should be searchable'):
        paths = list(echo.resolve_depends(registry))
    assert (target_field,) in paths
    label = VirtualDeleteTarget._meta.get_field('label')
    assert (target_field, label) in paths
