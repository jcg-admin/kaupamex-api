"""
Tests — Modelo PaymentGateway (UC-CFG-01), cifrado Fernet.

Cobertura reducida (2026-08): ``GatewayConnector``
(``addons.settings_app.gateway_connector``) y el CRUD admin
(``/api/v2/admin/gateways/``) desaparecieron con la disolucion del addon
``settings_app`` y no tienen homologo vivo (``grep -rn "GatewayConnector"
src/`` -> 0 hits; ``/api/v2/admin/gateways/`` no esta montado en
``config/urls.py``). Lo unico que sobrevive es el modelo ``PaymentGateway``
(movido a ``addons.payment.models``, tabla ``settings_payment_gateway``
intacta), con su cifrado Fernet de credenciales — eso es lo que este archivo
cubre ahora.
"""
import pytest

from addons.payment.models import PaymentGateway

pytestmark = pytest.mark.integration


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
