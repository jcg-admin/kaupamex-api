"""Historical nullable DDL must not query the current company model."""
import importlib
from unittest import mock

from django.db import connection, models
from django.db.migrations.state import ModelState, ProjectState
import pytest

from orm.environments import company_scope

from addons.hr.models.hr_payroll_structure_type import (
    ResCompany, _default_resource_calendar,
)

pytestmark = pytest.mark.django_db(transaction=True)


def test_calendar_migration_preserves_rows_without_live_defaults():
    assert connection.vendor == 'postgresql'
    migration = importlib.import_module(
        'addons.hr.migrations.0004_hrpayrollstructuretype_default_resource_calendar'
    ).Migration('0004_hrpayrollstructuretype_default_resource_calendar', 'hr')
    state = ProjectState()
    state.add_model(ModelState('resource', 'ResourceCalendar', [
        ('id', models.AutoField(primary_key=True)),
    ], options={'db_table': 'contract_calendar_migration_resource'}))
    state.add_model(ModelState('hr', 'HrPayrollStructureType', [
        ('id', models.AutoField(primary_key=True)),
        ('name', models.CharField(max_length=40)),
    ], options={'db_table': 'contract_calendar_migration_payroll'}))
    resource = state.apps.get_model('resource', 'ResourceCalendar')
    legacy = state.apps.get_model('hr', 'HrPayrollStructureType')
    with connection.schema_editor() as editor:
        editor.create_model(resource)
        editor.create_model(legacy)
    try:
        legacy.objects.create(name='Existing structure')
        with mock.patch.object(ResCompany.objects, 'filter', side_effect=AssertionError(
                'Historical DDL must not query live company schema')) as live_query, company_scope(7):
            with connection.schema_editor() as editor:
                after = migration.apply(state.clone(), editor)
            live_query.assert_not_called()
        current = after.apps.get_model('hr', 'HrPayrollStructureType')
        field = current._meta.get_field('default_resource_calendar')
        assert field.default is _default_resource_calendar
        assert field.null
        old = current.objects.get(name='Existing structure')
        assert old.default_resource_calendar_id is None
        with connection.schema_editor() as editor:
            migration.unapply(state.clone(), editor)
        assert legacy.objects.get().name == 'Existing structure'
    finally:
        with connection.schema_editor() as editor:
            editor.delete_model(legacy)
            editor.delete_model(resource)
