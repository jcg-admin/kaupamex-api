"""Contrato HTTP del catálogo técnico; no acredita instalación de módulos."""
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import include, path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from addons.authz.declaration import discover
from addons.authz.models import Capability, Module, Role, RoleAssignment
from addons.authz.services import invalidate_capabilities
from addons.base.models.ir_module import IrModule
from addons.base.controllers import admin_urls
from modules.db import create_categories


pytestmark = [pytest.mark.integration, pytest.mark.django_db]
URL = '/api/v2/admin/technical-modules/'


@pytest.fixture
def reader():
    user = get_user_model().objects.create_user(
        login='catalogue-reader@example.test', password='Catalogue-Test-123!',
    )
    module, _ = Module.objects.get_or_create(
        code='settings', defaults={'name': 'Configuración'},
    )
    capability, _ = Capability.objects.get_or_create(
        code='settings.modules', defaults={'module': module, 'name': 'Módulos'},
    )
    role = Role.objects.create(code='catalogue-reader', name='Lector de módulos')
    role.capabilities.add(capability)
    RoleAssignment.objects.create(user=user, role=role)
    invalidate_capabilities(user.pk)
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def catalogue():
    with connection.cursor() as cursor:
        sales_id = create_categories(cursor, ['Sales'])
        hidden_id = create_categories(cursor, ['Hidden'])
    return IrModule.objects.bulk_create([
        IrModule(name='fixture_catalog_alpha', shortdesc='Alpha',
                 category_id=sales_id, category_path='Sales', application=True, sequence=10,
                 version='19.0.2.0', state='uninstalled'),
        IrModule(name='fixture_catalog_beta', shortdesc='Beta',
                 category_id=sales_id, category_path='Sales', application=True, sequence=20,
                 version='19.0.2.0', installed_version='19.0.1.0',
                 state='installed'),
        IrModule(name='fixture_catalog_library', shortdesc='Library',
                 category_id=hidden_id, category_path='Hidden',
                 application=False, state='uninstalled'),
    ])


def test_catalogue_requires_session_and_explicit_capability():
    client = APIClient()
    assert client.get(URL).status_code == 401
    user = get_user_model().objects.create_user(
        login='catalogue-denied@example.test', password='Catalogue-Test-123!',
    )
    client.force_authenticate(user)
    assert client.get(URL).status_code == 403


def test_catalogue_paginates_without_implicit_application_filter(reader, catalogue):
    response = reader.get(URL, {'search': 'fixture_catalog_', 'page_size': 2})
    assert response.status_code == 200
    assert set(response.data) == {'count', 'next', 'previous', 'results'}
    assert response.data['count'] == 3
    assert [row['name'] for row in response.data['results']] == [
        'fixture_catalog_alpha', 'fixture_catalog_beta',
    ]
    assert response.data['next']
    second = reader.get(URL, {'search': 'fixture_catalog_', 'page_size': 2, 'page': 2})
    assert [row['name'] for row in second.data['results']] == ['fixture_catalog_library']


@pytest.mark.parametrize('filters, names', [
    ({'application': 'false'}, ['fixture_catalog_library']),
    ({'state': 'installed'}, ['fixture_catalog_beta']),
    ({'category': 'Sales'}, ['fixture_catalog_alpha', 'fixture_catalog_beta']),
])
def test_catalogue_filters_are_typed(reader, catalogue, filters, names):
    response = reader.get(URL, {'search': 'fixture_catalog_', **filters})
    assert response.status_code == 200
    assert [row['name'] for row in response.data['results']] == names


@pytest.mark.parametrize('query', [{'state': 'imaginary'}, {'database': 'other'}])
def test_catalogue_rejects_invalid_filters_and_database_selection(reader, query):
    response = reader.get(URL, query)
    assert response.status_code == 400
    assert 'codigo_error' in response.data


def test_catalogue_preserves_version_provenance_and_is_read_only(reader, catalogue):
    alpha, beta, _ = catalogue
    response = reader.get(f'{URL}{beta.pk}/')
    assert response.status_code == 200
    assert response.data['version'] == '19.0.2.0'
    assert response.data['category'] == 'Sales'
    assert response.data['installed_version'] == '19.0.1.0'
    assert reader.get(f'{URL}{alpha.pk}/').data['installed_version'] is None
    assert reader.get(f'{URL}999999999/').status_code == 404
    before = list(IrModule.objects.values_list('pk', 'state'))
    assert reader.post(URL, {'name': 'forbidden'}).status_code == 405
    assert reader.patch(f'{URL}{beta.pk}/', {'state': 'to upgrade'}).status_code == 405
    assert reader.delete(f'{URL}{beta.pk}/').status_code == 405
    assert list(IrModule.objects.values_list('pk', 'state')) == before


def test_catalogue_capability_is_declared_by_existing_collector():
    _, capabilities = discover()
    assert 'settings.modules' in capabilities


def test_catalogue_keeps_nested_category_text_and_exact_path_filter(reader):
    with connection.cursor() as cursor:
        category_id = create_categories(cursor, ['Contract Sales', 'Child'])
    row = IrModule.objects.create(
        name='fixture_catalog_nested', category_id=category_id,
        category_path='Contract Sales/Child',
    )
    response = reader.get(URL, {
        'search': row.name, 'category': 'Contract Sales/Child',
    })
    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['category'] == 'Contract Sales/Child'
    assert reader.get(URL, {'search': row.name, 'category': 'Child'}).data['count'] == 0


def test_catalogue_schema_publishes_paginated_read_only_session_contract():
    schema = SchemaGenerator(patterns=[
        path('api/v2/admin/', include(admin_urls.module_router.urls)),
    ]).get_schema(request=None, public=True)
    collection = schema['paths'][URL]
    assert set(collection) == {'get'}
    operation = collection['get']
    assert {'200', '400', '401', '403'} <= set(operation['responses'])
    assert operation['security'] == [{'cookieAuth': []}]
    response = operation['responses']['200']['content']['application/json']['schema']
    component = schema['components']['schemas'][response['$ref'].rsplit('/', 1)[1]]
    assert {'count', 'next', 'previous', 'results'} <= set(component['properties'])
    detail = schema['paths'][URL + '{id}/']
    assert set(detail) == {'get'}
    assert '404' in detail['get']['responses']
