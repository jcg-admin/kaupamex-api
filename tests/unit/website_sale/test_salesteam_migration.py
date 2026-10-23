"""Historical sales-team migration and runtime database binding contracts."""
from contextlib import contextmanager
from copy import deepcopy
import importlib
from unittest import mock

from django.conf import settings
from django.db import connections, models
from django.db.migrations.state import ModelState, ProjectState
from django.test.utils import CaptureQueriesContext
import pytest

from addons.base.models.ir_model import IrModelData
from addons.website_sale.models.website import (
    _default_salesteam_id, WEBSITE_SALESTEAM_XMLID,
)
from orm.environments import company_scope

ALIAS = 'company_77421_db'


@contextmanager
def historical_schema():
    assert connections['default'].vendor == 'postgresql'
    assert ALIAS not in settings.DATABASES
    configuration = deepcopy(settings.DATABASES['default'])
    with mock.patch.dict(settings.DATABASES, {ALIAS: configuration}):
        connections.databases[ALIAS] = configuration
        database = connections[ALIAS]
        state = ProjectState()
        definitions = [
            ('base', 'IrModelData', [('module', models.CharField(max_length=100)),
                                   ('name', models.CharField(max_length=100)),
                                   ('model', models.CharField(max_length=100)),
                                   ('res_id', models.IntegerField(null=True))]),
            ('sales_team', 'CrmTeam', [('active', models.BooleanField(default=True))]),
            ('mail', 'MailTemplate', []), ('website', 'Website', []),
            ('website_sale', 'WebsiteSaleSettings', [
                ('name', models.CharField(max_length=40)),
                ('cart_recovery_mail_template', models.ForeignKey(
                    'mail.MailTemplate', null=True, on_delete=models.SET_NULL))]),
            ('website_sale', 'WebsiteSaleOrderInfo', [
                ('website', models.ForeignKey('website.Website', on_delete=models.CASCADE))]),
        ]
        for app, name, fields in definitions:
            state.add_model(ModelState(app, name, [('id', models.AutoField(primary_key=True))]+fields,
                                       options={'db_table': 'contract_salesteam_'+name.lower()}))
        classes = [state.apps.get_model(app, name) for app, name, fields in definitions]
        with database.schema_editor() as editor:
            for model in classes:
                editor.create_model(model)
        try:
            yield database, state
        finally:
            with database.schema_editor() as editor:
                for model in reversed(classes):
                    editor.delete_model(model)
            database.close()
            del connections[ALIAS]
            connections.databases.pop(ALIAS, None)


def migration(number):
    name = ('0003_websitesalesettings_salesteam_and_more' if number == 3 else
            '0004_remove_websitesalesettings_website_sale_salesteam_nn_and_more')
    result = importlib.import_module('addons.website_sale.migrations.'+name).Migration(name, 'website_sale')
    result.operations = deepcopy(result.operations)
    # The fixture must not collide with the real migrated application's index.
    for operation in result.operations:
        if hasattr(operation, 'index'):
            operation.index.name = 'contract_salesteam_nn'
        elif getattr(operation, 'name', None) == 'website_sale_salesteam_nn':
            operation.name = 'contract_salesteam_nn'
    return result


@pytest.mark.parametrize('team_state', [None, True, False, 'missing', 'wrong_model'])
@pytest.mark.django_db(transaction=True)
def test_historical_migration_preserves_local_default_without_live_models(team_state):
    with historical_schema() as (database, state), company_scope(77421):
        metadata = state.apps.get_model('base', 'IrModelData')
        teams = state.apps.get_model('sales_team', 'CrmTeam')
        legacy = state.apps.get_model('website_sale', 'WebsiteSaleSettings')
        legacy.objects.using(ALIAS).create(name='Existing site')
        expected = None
        if team_state is not None:
            team = teams.objects.using(ALIAS).create(active=team_state is True)
            metadata.objects.using(ALIAS).create(
                module='sales_team', name='salesteam_website_sales',
                model='base.ResPartner' if team_state == 'wrong_model' else 'sales_team.CrmTeam',
                res_id=999999 if team_state == 'missing' else team.pk)
            expected = team.pk if team_state is True else None
        third, fourth = migration(3), migration(4)
        with mock.patch.object(IrModelData, 'ref', side_effect=AssertionError(
                'Historical DDL must not query runtime XMLID models')) as live_lookup, \
                CaptureQueriesContext(connections['default']) as central_queries:
            if team_state == 'wrong_model':
                with pytest.raises(ValueError, match='different historical model'):
                    with database.schema_editor() as editor:
                        third.apply(state.clone(), editor)
                assert legacy.objects.using(ALIAS).get().name == 'Existing site'
                live_lookup.assert_not_called()
                assert not central_queries.captured_queries
                return
            with database.schema_editor() as editor:
                after_third = third.apply(state.clone(), editor)
            current = after_third.apps.get_model('website_sale', 'WebsiteSaleSettings')
            field = current._meta.get_field('salesteam')
            assert field.default is _default_salesteam_id and field.null
            assert current.objects.using(ALIAS).get().salesteam_id == expected
            with database.schema_editor() as editor:
                after_fourth = fourth.apply(after_third.clone(), editor)
            current = after_fourth.apps.get_model('website_sale', 'WebsiteSaleSettings')
            field = current._meta.get_field('salesteam_id')
            assert field.default is _default_salesteam_id and field.null
            assert getattr(current.objects.using(ALIAS).get(), field.attname) == expected
            with database.cursor() as cursor:
                cursor.execute('SELECT pg_get_expr(indpred, indrelid) FROM pg_index '
                               'JOIN pg_class ON pg_class.oid=indexrelid WHERE relname=%s',
                               ['contract_salesteam_nn'])
                assert 'IS NOT NULL' in cursor.fetchone()[0]
            with database.schema_editor() as editor:
                fourth.unapply(after_third.clone(), editor)
            with database.schema_editor() as editor:
                third.unapply(state.clone(), editor)
            assert legacy.objects.using(ALIAS).get().name == 'Existing site'
            live_lookup.assert_not_called()
            assert not central_queries.captured_queries


@pytest.mark.parametrize('company,expected', [(None, 'default'), (77421, ALIAS)])
def test_runtime_default_uses_existing_router_binding(company, expected):
    extra = {ALIAS: deepcopy(settings.DATABASES['default'])} if company is not None else {}
    with mock.patch.dict(settings.DATABASES, extra), \
            company_scope(company), mock.patch.object(IrModelData, 'ref', return_value=None) as reference:
        assert _default_salesteam_id() is None
        reference.assert_called_once_with(WEBSITE_SALESTEAM_XMLID,
                                          raise_if_not_found=False, using=expected)
