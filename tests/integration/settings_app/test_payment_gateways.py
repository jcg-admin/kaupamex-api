"""
Tests — Payment gateways and shipping methods configuration

UC-CFG-01: Configure payment gateways
UC-CFG-02: Configure shipping methods and costs
"""
import pytest
from decimal import Decimal
from addons.settings_app.models import ShippingMethod
from addons.payment.models import PaymentGateway
from addons.settings_app.gateway_connector import GatewayConnector

pytestmark = pytest.mark.integration

GATEWAYS_URL  = '/api/v2/admin/gateways/'
SHIPPING_URL  = '/api/v2/admin/shipping-methods/'


# =============================================================================
# Modelo PaymentGateway — cifrado Fernet
# =============================================================================

class TestPaymentGatewayModel:

    def test_set_y_get_credentials_roundtrip(self, db):
        gw = PaymentGateway.objects.create(gateway='MERCADOPAGO', name='MercadoPago', is_active=False)
        gw.set_credentials({'access_token': 'TEST-VALID-abc123', 'public_key': 'pk-test'})
        gw.save()
        gw.refresh_from_db()
        creds = gw.get_credentials()
        assert creds['access_token'] == 'TEST-VALID-abc123'
        assert creds['public_key'] == 'pk-test'

    def test_credentials_no_es_el_valor_en_claro(self, db):
        gw = PaymentGateway.objects.create(gateway='PAYPAL', name='PayPal', is_active=False)
        gw.set_credentials({'client_id': 'TEST-VALID-client', 'client_secret': 'supersecret'})
        gw.save()
        assert 'supersecret' not in str(gw.credentials)  # BinaryField

    def test_get_masked_credentials_enmascara(self, db):
        gw = PaymentGateway(gateway='MERCADOPAGO', name='MercadoPago')
        gw.set_credentials({'access_token': 'ABCD1234EFGH'})
        masked = gw.get_masked_credentials()
        assert '****' in masked['access_token']  # formato: parcial****parcial
        assert masked['access_token'].endswith('EFGH')

    def test_get_credentials_sin_datos_retorna_dict_vacio(self, db):
        gw = PaymentGateway(gateway='MERCADOPAGO', name='MercadoPago', credentials=b'')
        assert gw.get_credentials() == {}


# =============================================================================
# GatewayConnector mock
# =============================================================================

class TestGatewayConnectorMock:

    def test_mp_token_test_valid_retorna_true(self):
        c = GatewayConnector()
        assert c.verify_mercadopago('TEST-VALID-xyz') is True

    def test_mp_token_test_invalid_retorna_false(self):
        c = GatewayConnector()
        assert c.verify_mercadopago('TEST-INVALID-xyz') is False

    def test_mp_token_vacio_retorna_false(self):
        c = GatewayConnector()
        assert c.verify_mercadopago('') is False

    def test_pp_client_id_test_valid_retorna_true(self):
        c = GatewayConnector()
        assert c.verify_paypal('TEST-VALID-id', 'some-secret') is True

    def test_pp_client_id_test_invalid_retorna_false(self):
        c = GatewayConnector()
        assert c.verify_paypal('TEST-INVALID-id', 'some-secret') is False


# =============================================================================
# UC-CFG-01 — PaymentGatewayViewSet
# =============================================================================

class TestPaymentGatewayAPI:

    def test_listar_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(GATEWAYS_URL)
        assert res.status_code == 401

    def test_listar_usuario_normal_retorna_403(self, auth_client, db):
        res = auth_client.get(GATEWAYS_URL)
        assert res.status_code == 403

    def test_listar_admin_retorna_200(self, admin_client, db):
        res = admin_client.get(GATEWAYS_URL)
        assert res.status_code == 200

    def test_crear_gateway_mp(self, admin_client, db):
        res = admin_client.post(GATEWAYS_URL, {
            'gateway': 'MERCADOPAGO', 'name': 'MercadoPago Test',
            'is_active': False,
            'credentials_raw': {'access_token': 'TEST-VALID-token123'},
        }, format='json')
        assert res.status_code == 201
        assert res.json()['gateway'] == 'MERCADOPAGO'

    def test_credenciales_enmascaradas_en_respuesta(self, admin_client, db):
        admin_client.post(GATEWAYS_URL, {
            'gateway': 'PAYPAL', 'name': 'PayPal Test',
            'is_active': False,
            'credentials_raw': {'client_id': 'TEST-VALID-cid', 'client_secret': 'sup3rs3cr3t'},
        }, format='json')
        res = admin_client.get(GATEWAYS_URL)
        gateway = next(g for g in res.json() if g['gateway'] == 'PAYPAL')
        creds = gateway['credentials']
        # El secret no debe aparecer en claro
        assert 'sup3rs3cr3t' not in str(creds)
        assert creds.get('client_secret', '').startswith('*')

    def test_credentials_raw_no_aparece_en_respuesta(self, admin_client, db):
        res = admin_client.post(GATEWAYS_URL, {
            'gateway': 'MERCADOPAGO', 'name': 'MercadoPago Test',
            'is_active': False,
            'credentials_raw': {'access_token': 'TEST-VALID-tk'},
        }, format='json')
        assert 'credentials_raw' not in res.json()
        assert 'TEST-VALID-tk' not in str(res.json())

    def test_verify_endpoint_con_credenciales_validas(self, admin_client, db):
        created = admin_client.post(GATEWAYS_URL, {
            'gateway': 'MERCADOPAGO', 'name': 'MercadoPago Test',
            'is_active': False,
            'credentials_raw': {'access_token': 'TEST-VALID-abc'},
        }, format='json').json()
        res = admin_client.post(f'{GATEWAYS_URL}{created["id"]}/verify/')
        assert res.status_code == 200
        assert 'verified_at' in res.json()

    def test_verify_endpoint_con_credenciales_invalidas(self, admin_client, db):
        created = admin_client.post(GATEWAYS_URL, {
            'gateway': 'MERCADOPAGO', 'name': 'MercadoPago Test',
            'is_active': False,
            'credentials_raw': {'access_token': 'TEST-INVALID-abc'},
        }, format='json').json()
        res = admin_client.post(f'{GATEWAYS_URL}{created["id"]}/verify/')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_CREDENTIALS'

    def test_provider_unico_no_permite_duplicado(self, admin_client, db):
        admin_client.post(GATEWAYS_URL, {
            'gateway': 'MERCADOPAGO', 'name': 'MercadoPago Test', 'is_active': False,
            'credentials_raw': {},
        }, format='json')
        res = admin_client.post(GATEWAYS_URL, {
            'gateway': 'MERCADOPAGO', 'name': 'MercadoPago Test', 'is_active': False,
            'credentials_raw': {},
        }, format='json')
        assert res.status_code == 400


# =============================================================================
# UC-CFG-02 — ShippingMethodViewSet
# =============================================================================

class TestShippingMethodAPI:

    def test_crear_metodo_envio(self, admin_client, db):
        res = admin_client.post(SHIPPING_URL, {
            'name': 'Express 24h',
            'description': 'Entrega en un día hábil',
            'cost': '150.00',
            'estimated_days': 1,
            'is_active': True,
        }, format='json')
        assert res.status_code == 201
        data = res.json()
        assert data['name'] == 'Express 24h'
        assert data['estimated_days'] == 1

    def test_crear_metodo_envio_gratis(self, admin_client, db):
        res = admin_client.post(SHIPPING_URL, {
            'name': 'Estándar Gratis',
            'cost': '0.00',
            'estimated_days': 5,
            'free_threshold': '800.00',
        }, format='json')
        assert res.status_code == 201
        assert res.json()['free_threshold'] == '800.00'

    def test_costo_negativo_retorna_400(self, admin_client, db):
        res = admin_client.post(SHIPPING_URL, {
            'name': 'Invalido', 'cost': '-10.00', 'estimated_days': 3,
        }, format='json')
        assert res.status_code == 400

    def test_dias_cero_retorna_400(self, admin_client, db):
        res = admin_client.post(SHIPPING_URL, {
            'name': 'Invalido', 'cost': '50.00', 'estimated_days': 0,
        }, format='json')
        assert res.status_code == 400

    def test_editar_metodo_envio(self, admin_client, db):
        created = admin_client.post(SHIPPING_URL, {
            'name': 'Normal', 'cost': '80.00', 'estimated_days': 3,
        }, format='json').json()
        res = admin_client.patch(
            f'{SHIPPING_URL}{created["id"]}/',
            {'cost': '90.00'}, format='json'
        )
        assert res.status_code == 200
        assert res.json()['cost'] == '90.00'

    def test_desactivar_metodo_soft_delete(self, admin_client, db):
        created = admin_client.post(SHIPPING_URL, {
            'name': 'A Desactivar', 'cost': '60.00', 'estimated_days': 2,
        }, format='json').json()
        res = admin_client.delete(f'{SHIPPING_URL}{created["id"]}/')
        assert res.status_code == 204
        sm = ShippingMethod.objects.get(pk=created['id'])
        assert sm.is_active is False

    def test_listar_incluye_activos_e_inactivos(self, admin_client, db):
        admin_client.post(SHIPPING_URL, {
            'name': 'Activo', 'cost': '50.00', 'estimated_days': 3,
        }, format='json')
        res = admin_client.get(SHIPPING_URL)
        assert res.status_code == 200
        assert len(res.json()) >= 1

    def test_zonas_como_json(self, admin_client, db):
        res = admin_client.post(SHIPPING_URL, {
            'name': 'Zona Norte', 'cost': '120.00', 'estimated_days': 4,
            'zones': ['MX-CMX', 'MX-JAL'],
        }, format='json')
        assert res.status_code == 201
        assert 'MX-CMX' in res.json()['zones']
