"""
Tests de integración — Schema OpenAPI (drf-spectacular)

Verifica que el endpoint /api/schema/ funciona y genera un schema
OpenAPI 3.0 válido con los componentes esperados del Sprint 1.
"""
import pytest

pytestmark = pytest.mark.api


class TestSchemaEndpoint:
    """El endpoint /api/schema/ genera OpenAPI 3.0 válido."""

    def test_schema_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/')
        assert r.status_code == 200

    def test_schema_contiene_claves_openapi(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        data = r.json()
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data

    def test_schema_version_correcta(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        assert r.json()['info']['version'] == '1.0.0'

    def test_schema_titulo_correcto(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        assert 'PracticaYoruba' in r.json()['info']['title']

    def test_schema_contiene_endpoints_auth(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        paths = r.json()['paths']
        assert '/api/v1/auth/login/' in paths
        assert '/api/v1/auth/register/' in paths
        assert '/api/v1/auth/logout/' in paths

    def test_schema_contiene_endpoint_config(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        paths = r.json()['paths']
        assert '/api/v1/config/settings/' in paths

    def test_schema_register_tiene_request_body(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        register = r.json()['paths']['/api/v1/auth/register/']['post']
        assert 'requestBody' in register

    def test_schema_config_settings_patch_tiene_request(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        settings = r.json()['paths']['/api/v1/config/settings/']['patch']
        assert 'requestBody' in settings

    def test_schema_tiene_esquema_jwt(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        schemas = r.json().get('components', {}).get('securitySchemes', {})
        assert 'jwtAuth' in schemas


class TestSwaggerUI:
    """La Swagger UI responde correctamente."""

    def test_swagger_ui_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/swagger-ui/')
        assert r.status_code == 200


class TestRedocUI:
    """La Redoc UI responde correctamente."""

    def test_redoc_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/redoc/')
        assert r.status_code == 200
