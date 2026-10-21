"""Contrato compute de ResGroups: asignación, caché y diagnóstico sin recursión."""
from unittest.mock import patch

import pytest
from django.apps import apps

from orm.environments import context_scope, env, transaction_scope
from orm import registry


@pytest.fixture
def group():
    registry.field_depends_context.clear()
    try:
        with transaction_scope():
            yield apps.get_model('base', 'ResGroups')(name='Operations')
    finally:
        # Los mocks de compute no deben conservar metadata derivada entre casos.
        registry.field_depends_context.clear()


def test_first_and_second_reads_compute_once(group):
    method = type(group)._compute_full_name
    with patch.object(type(group), '_compute_full_name', autospec=True,
                      side_effect=method) as compute:
        compute._depends = method._depends
        compute._depends_context = method._depends_context
        registry.field_depends_context.clear()
        assert group.full_name == 'Operations'
        assert group.full_name == 'Operations'
        assert compute.call_count == 1


def test_compute_assigns_instead_of_returning(group):
    assert group._compute_full_name() is None
    assert group.full_name == 'Operations'


def test_privilege_prefix_uses_real_consumer(group):
    privilege = apps.get_model('base', 'ResGroupsPrivilege')(pk=43, name='Admin')
    group.privilege = privilege
    assert group.full_name == 'Admin / Operations'


def test_short_display_name_omits_privilege(group):
    group.privilege = apps.get_model('base', 'ResGroupsPrivilege')(pk=43, name='Admin')
    with context_scope(short_display_name=True):
        assert group.full_name == 'Operations'


def test_cache_invalidation_allows_recomputation(group):
    group.pk = 37
    field = group._meta.get_field('full_name')
    assert group.full_name == 'Operations'
    assert field._get_cache(env())[37] == 'Operations'
    group.name = 'Support'
    # El almacén Django y la caché transaccional son planos distintos.
    group.__dict__.pop(field.attname, None)
    field._invalidate_cache(env(), [37])
    assert group.full_name == 'Support'
    assert field._get_cache(env())[37] == 'Support'


def test_compute_declares_reference_dependencies(group):
    method = type(group)._compute_full_name
    assert set(method._depends) == {'privilege.name', 'name'}
    assert method._depends_context == ('short_display_name',)


def test_return_without_assignment_raises_without_recursive_label(group):
    with patch.object(type(group), '_compute_full_name', return_value='ignored'):
        with pytest.raises(ValueError, match='Compute method failed to assign'):
            group.full_name


def test_compute_exception_is_not_swallowed(group):
    with patch.object(type(group), '_compute_full_name', side_effect=RuntimeError('compute failed')):
        with pytest.raises(RuntimeError, match='compute failed'):
            group.full_name


def test_context_buckets_do_not_reuse_the_instance_label(group):
    group.pk = 37
    group.privilege = apps.get_model('base', 'ResGroupsPrivilege')(pk=43, name='Admin')
    assert group.full_name == 'Admin / Operations'
    with context_scope(short_display_name=True):
        assert group.full_name == 'Operations'
    assert group.full_name == 'Admin / Operations'


def test_cache_key_uses_dependencies_derived_from_the_compute(group):
    field = group._meta.get_field('full_name')
    assert env().cache_key(field) == (None,)
    with context_scope(short_display_name=True):
        assert env().cache_key(field) == (True,)


def test_unsaved_context_switch_preserves_each_cached_value(group):
    group.privilege = apps.get_model('base', 'ResGroupsPrivilege')(pk=43, name='Admin')
    group.full_name = 'Explicit normal-context label'
    assert group.full_name == 'Explicit normal-context label'
    with context_scope(short_display_name=True):
        assert group.full_name == 'Operations'
    assert group.full_name == 'Explicit normal-context label'
    assert group.pk is None


def test_unsaved_instances_have_separate_contextual_values(group):
    other = type(group)(name='Support')
    assert group.full_name == 'Operations'
    assert other.full_name == 'Support'
    assert group.full_name == 'Operations'
    field = group._meta.get_field('full_name')
    cache = field._get_cache(env())
    assert len(cache) == 2
    assert None not in cache
    assert group.pk is None and other.pk is None


def test_constructor_contextual_value_seeds_only_its_context(group):
    record = type(group)(name='Support', full_name='Constructor label')
    assert record.full_name == 'Constructor label'
    with context_scope(short_display_name=True):
        assert record.full_name == 'Support'
    assert record.full_name == 'Constructor label'


def test_virtual_cache_invalidation_recomputes_instead_of_using_instance_value(group):
    assert group.full_name == 'Operations'
    field = group._meta.get_field('full_name')
    group.name = 'Support'
    field._invalidate_cache(env())
    assert group.full_name == 'Support'


def test_invalidated_virtual_value_does_not_hide_missing_assignment(group):
    assert group.full_name == 'Operations'
    field = group._meta.get_field('full_name')
    field._invalidate_cache(env())
    with patch.object(type(group), '_compute_full_name', return_value='ignored'):
        with pytest.raises(ValueError, match='Compute method failed to assign'):
            group.full_name


def test_virtual_compute_keeps_recursive_read_protection(group):
    observed = []
    original = type(group)._compute_full_name

    def compute(record):
        observed.append(record.full_name)
        record.full_name = 'Protected computation'

    compute._depends = original._depends
    compute._depends_context = original._depends_context
    with patch.object(type(group), '_compute_full_name', compute):
        assert group.full_name == 'Protected computation'
    assert observed == [False]
