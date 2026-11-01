"""Attached record environments govern computed values and their cache.

No SQL is needed. These controls cover descriptor/environment integration,
not database routing or the full field access-control contract.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, local

from django.db import models
import pytest

import api
import fields
from orm import registry
from orm.environments import (
    context_scope,
    env as ambient_env,
    get_context,
    is_su,
    transaction_scope,
)
from orm.fields import FieldDescriptor
from orm.models import BaseModel


class RecordEnvironmentProbe(BaseModel):
    _name = 'orm.record.environment.probe'
    rendered = fields.Char(compute='_compute_rendered')
    ambient_value = fields.Char(compute='_compute_ambient_value')
    failing = fields.Char(compute='_compute_failing')
    privileged = fields.Boolean(compute='_compute_privileged')
    sudo_value = fields.Boolean(
        compute='_compute_sudo_value', compute_sudo=True
    )

    class Meta:
        app_label = 'contenttypes'
        managed = False

    @api.depends_context('probe_key')
    def _compute_rendered(self):
        self.rendered = self.env.context.get('probe_key', 'missing')

    @api.depends_context('probe_key')
    def _compute_ambient_value(self):
        self.ambient_value = get_context().get('probe_key', 'missing')

    @api.depends_context('probe_key')
    def _compute_failing(self):
        raise RuntimeError('compute failed')

    @api.depends_context('uid')
    def _compute_privileged(self):
        self.privileged = is_su()

    @api.depends_context('uid')
    def _compute_sudo_value(self):
        self.sudo_value = self.env.su


class AmbientRowProbe(models.Model):
    value = fields.Char(max_length=32)

    class Meta:
        app_label = 'contenttypes'
        managed = False


@pytest.fixture(autouse=True)
def isolated_environment():
    with transaction_scope(), context_scope(probe_key='ambient'):
        registry.clear_field_depends()
        yield
        registry.clear_field_depends()


def record():
    return RecordEnvironmentProbe._from_ids(ambient_env(), (31,), (31,))


def test_with_context_separates_computed_values_for_the_same_id():
    source = record()
    red = source.with_context(probe_key='red')
    blue = source.with_context(probe_key='blue')
    assert red.rendered == 'red'
    assert blue.rendered == 'blue'
    assert red.rendered == 'red'
    field = RecordEnvironmentProbe._meta.get_field('rendered')
    assert field._get_cache(red.env)[31] == 'red'
    assert field._get_cache(blue.env)[31] == 'blue'


def test_ambient_helpers_see_attached_context_during_compute_only():
    attached = record().with_context(probe_key='attached')
    assert attached.ambient_value == 'attached'
    assert get_context()['probe_key'] == 'ambient'


def test_explicit_assignment_uses_the_attached_cache_bucket():
    attached = record().with_context(probe_key='attached')
    attached.rendered = 'assigned'
    field = RecordEnvironmentProbe._meta.get_field('rendered')
    assert field._get_cache(attached.env)[31] == 'assigned'
    assert 31 not in field._get_cache(ambient_env())


def test_compute_exception_restores_ambient_context_and_scope_frames():
    attached = record().with_context(probe_key='attached')
    with pytest.raises(RuntimeError, match='compute failed'):
        _ = attached.failing
    assert get_context()['probe_key'] == 'ambient'
    assert not attached.env._tokens


def test_sudo_bucket_and_channel_do_not_leak_to_the_ambient_record():
    ordinary = record()
    elevated = ordinary.sudo()
    assert ordinary.privileged is False
    assert elevated.privileged is True
    assert ordinary.privileged is False
    assert is_su() is False


def test_class_access_preserves_the_descriptor():
    assert isinstance(RecordEnvironmentProbe.rendered, FieldDescriptor)


def test_plain_django_instance_keeps_its_existing_value():
    assert AmbientRowProbe(value='ordinary').value == 'ordinary'


def test_shared_attached_environment_scopes_are_local_to_each_thread(
    monkeypatch,
):
    attached = record().with_context(probe_key='attached')
    assert attached.rendered == 'attached'
    first_entered = Event()
    second_entered = Event()
    first_finished = Event()
    worker = local()

    @api.depends_context('probe_key')
    def compute(instance):
        if worker.role == 'first':
            first_entered.set()
            assert second_entered.wait(timeout=5)
        else:
            assert first_entered.wait(timeout=5)
            second_entered.set()
            assert first_finished.wait(timeout=5)
        instance.rendered = get_context()['probe_key']

    monkeypatch.setattr(RecordEnvironmentProbe, '_compute_rendered', compute)

    def read(role):
        worker.role = role
        try:
            value = attached.rendered
            return value, get_context().get('probe_key')
        finally:
            if role == 'first':
                first_finished.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(read, role) for role in ('first', 'second')]
        results = [future.result(timeout=8) for future in futures]
    assert results == [('attached', None), ('attached', None)]
    assert get_context()['probe_key'] == 'ambient'
    assert not attached.env._tokens


@pytest.mark.parametrize('attached_context', [False, True])
def test_compute_sudo_receives_an_elevated_record_and_restores_the_caller(
    monkeypatch, attached_context,
):
    observed = []

    @api.depends_context('uid')
    def compute(instance):
        observed.append((instance.env.su, is_su()))
        instance.sudo_value = instance.env.su

    monkeypatch.setattr(RecordEnvironmentProbe, '_compute_sudo_value', compute)
    ordinary = record()
    if attached_context:
        ordinary = ordinary.with_context(probe_key='attached')
    assert ordinary.sudo_value is True
    assert observed == [(True, True)]
    assert ordinary.env.su is False
    assert is_su() is False


@pytest.mark.parametrize('attached_context', [False, True])
def test_compute_sudo_assignment_keeps_the_elevated_channel(
    monkeypatch, attached_context,
):
    field = RecordEnvironmentProbe._meta.get_field('sudo_value')
    original = field.write
    observed = []

    def write(records, value):
        observed.append(is_su())
        return original(records, value)

    @api.depends_context('uid')
    def compute(instance):
        instance.sudo_value = True

    monkeypatch.setattr(field, 'write', write)
    monkeypatch.setattr(RecordEnvironmentProbe, '_compute_sudo_value', compute)
    ordinary = record()
    if attached_context:
        ordinary = ordinary.with_context(probe_key='attached')
    assert ordinary.sudo_value is True
    assert observed == [True]
    assert is_su() is False
