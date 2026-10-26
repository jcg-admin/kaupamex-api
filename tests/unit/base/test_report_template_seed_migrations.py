"""Late seeds must obey the existing base.0070 view-type contract."""
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.utils.connection import ConnectionDoesNotExist

from addons.base.models.ir_ui_view import IrUiView


CASES = [
    ('sale', '0013_align_report_template_type', 'sale.report_saleorder'),
    ('sale_stock', '0004_align_report_template_type',
     'sale_stock.report_saleorder_incoterm'),
]
pytestmark = pytest.mark.django_db


@pytest.fixture
def historical_apps():
    return MigrationLoader(connection).project_state([
        (app, name) for app, name, _key in CASES
    ]).apps


@pytest.mark.parametrize('app,name,key', CASES)
def test_upgrade_preserves_every_non_type_value(app, name, key, historical_apps):
    migration = import_module(f'addons.{app}.migrations.{name}')
    row = IrUiView.objects.get(key=key)
    IrUiView.objects.filter(pk=row.pk).update(type='qweb')
    before = IrUiView.objects.filter(pk=row.pk).values().get()
    with connection.schema_editor() as editor:
        migration.align_report_template_type(historical_apps, editor)
    after = IrUiView.objects.filter(pk=row.pk).values().get()
    assert before.pop('type') == 'qweb'
    assert after.pop('type') == 'template'
    assert after == before
    with connection.schema_editor() as editor:
        migration.align_report_template_type(historical_apps, editor)
    assert IrUiView.objects.filter(pk=row.pk).values().get() == {
        **after, 'type': 'template',
    }


@pytest.mark.parametrize('app,name,key', CASES)
def test_upgrade_is_scoped_to_owned_key(app, name, key, historical_apps):
    migration = import_module(f'addons.{app}.migrations.{name}')
    other = IrUiView.objects.create(
        key=f'test.unrelated.{app}', name='Unrelated legacy view',
        type='qweb', arch_db='<descriptor/>', mode='primary',
    )
    IrUiView.objects.filter(key=key).update(type='form')
    before = list(IrUiView.objects.order_by('pk').values())
    with connection.schema_editor() as editor:
        migration.align_report_template_type(historical_apps, editor)
    assert list(IrUiView.objects.order_by('pk').values()) == before
    assert IrUiView.objects.get(pk=other.pk).type == 'qweb'


@pytest.mark.parametrize('app,name,key', CASES)
def test_missing_alias_never_falls_back_to_default(app, name, key, historical_apps):
    migration = import_module(f'addons.{app}.migrations.{name}')

    def reject_default(execute, sql, params, many, context):
        pytest.fail('Migration fell back to default connection')

    editor = SimpleNamespace(connection=SimpleNamespace(
        alias='unconfigured_report_seed_alias'))
    with connection.execute_wrapper(reject_default):
        with pytest.raises(ConnectionDoesNotExist):
            migration.align_report_template_type(historical_apps, editor)


@pytest.mark.parametrize('app,name,key', CASES)
def test_graph_orders_repair_after_seed_and_canonical_mapping(app, name, key):
    loader = MigrationLoader(connection)
    plan = loader.graph.forwards_plan((app, name))
    assert plan.index(('base', '0070_view_type_qweb_to_template')) < plan.index((app, name))
    seed = ('sale', '0002_seed_report_saleorder_view') if app == 'sale' else (
        'sale_stock', '0003_seed_report_incoterm_extension')
    assert plan.index(seed) < plan.index((app, name))
