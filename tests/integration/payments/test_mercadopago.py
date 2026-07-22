"""
Tests — MercadoPago payment, MSI installments and express checkout

UC-PAY-01:     Process payment with MercadoPago
UC-PAY-01-EXT: MSI installment plans
UC-ORD-01-EXT: Express checkout
"""
import json
import uuid
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from decouple import config
from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress, ShippingZone
from addons.delivery.models import ShippingMethod
from addons.payment.models import PaymentGateway
from addons.payment.models import Payment, PaymentGatewayEvent
from addons.payment_mercado_pago.gateway import MercadoPagoGateway
from addons.users.models import Address

pytestmark = pytest.mark.integration

INITIATE_URL    = '/api/v1/payments/initiate/'
INSTALLMENT_URL = '/api/v2/payments/installments/'
ELIGIBILITY_URL = '/api/v2/checkout/eligibility/'
EXPRESS_URL     = '/api/v2/checkout/express/'


# =============================================================================
# Fixtures compartidos
# =============================================================================

@pytest.fixture
def cat_s15(db):
    return Category.objects.create(name='Cat S15', slug='cat-s15', is_active=True)


@pytest.fixture
def prod_s15(db, cat_s15):
    _p = Product.objects.create(
        name='Prod S15', slug='prod-s15', sku='S15-001',
        description='',
        price=Decimal('1500.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_s15)
    return _p


@pytest.fixture
def orden_pendiente(db, user, prod_s15):
    """Orden en estado PENDING con OrderValue."""
    order = Order.objects.create(
        user=user, status='PENDING',
    )
    OrderItem.objects.create(
        order=order, product_name=prod_s15.name,
        sku=prod_s15.sku, unit_price=prod_s15.price,
        quantity=2, subtotal=prod_s15.price * 2,
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('3000.00'),
        tax=Decimal('413.79'), shipping_cost=Decimal('0.00'),
        discount=Decimal('0.00'), total=Decimal('3000.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test User',
        street='Av. Reforma 100', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


@pytest.fixture
def mp_gateway_activo(db, admin_user):
    """PaymentGateway de MercadoPago activo con credenciales de prueba."""
    gw = PaymentGateway(
        name='MercadoPago Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': config('MP_TEST_ACCESS_TOKEN', default='TEST-ACCESS-TOKEN-FAKE'),
        'public_key':   config('MP_TEST_PUBLIC_KEY',   default='TEST-PUBLIC-KEY-FAKE'),
    })
    gw.save()
    return gw


@pytest.fixture
def mock_mp_sdk():
    """Mock del SDK de MercadoPago para evitar llamadas reales."""
    with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
        sdk_instance = MagicMock()
        mock_mp.SDK.return_value = sdk_instance

        # Mock de preference().create()
        sdk_instance.preference.return_value.create.return_value = {
            'status': 201,
            'response': {
                'id':          'PREF-TEST-123456',
                'init_point':  'https://www.mercadopago.com.mx/checkout/v1/redirect?pref_id=PREF-TEST-123456',
                'sandbox_init_point': 'https://sandbox.mercadopago.com.mx/checkout/v1/redirect?pref_id=PREF-TEST-123456',
            },
        }
        # Mock de payment().get()
        sdk_instance.payment.return_value.get.return_value = {
            'status': 200,
            'response': {
                'id':                 12345678,
                'status':             'approved',
                'transaction_amount': 3000.00,
                'installments':       1,
            },
        }
        # Mock de payment_methods().list_all()
        sdk_instance.payment_methods.return_value.list_all.return_value = {
            'status': 200,
            'response': [
                {
                    'payment_type_id': 'credit_card',
                    'payer_costs': [
                        {'installments': 3,  'installment_rate': 0, 'min_allowed_amount': 100},
                        {'installments': 6,  'installment_rate': 0, 'min_allowed_amount': 200},
                        {'installments': 12, 'installment_rate': 0, 'min_allowed_amount': 500},
                        {'installments': 2,  'installment_rate': 5.99},  # con interés — excluir
                    ],
                }
            ],
        }
        yield sdk_instance


# =============================================================================
# UC-PAY-01 — Procesar Pago con MercadoPago
# =============================================================================

class TestIniciarPago:

    def test_iniciar_pago_sin_auth_retorna_401(self, api_client, db):
        res = api_client.post(INITIATE_URL, {}, format='json')
        assert res.status_code == 401

    def test_iniciar_pago_orden_ajena_retorna_404(
        self, api_client, orden_pendiente, mp_gateway_activo, db, django_user_model,
    ):
        """T-304 / DEC-BC-11: usuario autenticado NO puede iniciar pago
        sobre la orden de OTRO usuario.

        El audit T-101 UC-PAY-01 D-09/D-14 detecto que el InitiatePaymentView
        tenia un branch `else` (no autenticado) que ejecutaba
        ``Order.objects.get(order_number=...)`` SIN filtro ``user=``. Era
        codigo muerto bajo ``IsAuthenticated`` (vector latente) pero
        habria sido fraude si alguien cambiaba la permission a AllowAny
        sin tocar el branch.

        Tras el fix (collapse a un solo Order.objects.get con filtro
        ``user=request.user``), un comprador autenticado distinto al
        dueno no encuentra la orden y recibe ORDER_NOT_FOUND.
        """
        # Crear otro usuario que intentara pagar la orden de `user`
        attacker = django_user_model.objects.create_user(
            email='attacker@test.mx',
            password='AttackPass123!',
        )
        api_client.force_authenticate(user=attacker)
        res = api_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')
        assert res.status_code == 400, (
            f'Esperado 400 ORDER_NOT_FOUND (filtro user= excluye orden ajena), '
            f'recibido {res.status_code}: {res.json() if hasattr(res, "json") else res.content}'
        )
        body = res.json()
        assert body.get('codigo_error') == 'ORDER_NOT_FOUND'

    def test_iniciar_pago_crea_payment_y_retorna_checkout_url(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')
        assert res.status_code == 201, res.json()
        data = res.json()
        assert 'checkout_url' in data
        assert data['checkout_url'].startswith('https://')
        assert data['order_number'] == orden_pendiente.order_number
        assert data['installments'] == 1

    def test_iniciar_pago_crea_registro_payment_en_bd(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')
        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.status == 'PENDING'
        assert payment.preference_id == 'PREF-TEST-123456'
        assert payment.gateway == 'MERCADOPAGO'

    def test_iniciar_pago_registra_evento_de_auditoria(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')
        payment = Payment.objects.get(order=orden_pendiente)
        event = PaymentGatewayEvent.objects.filter(
            payment=payment, event_type='PREFERENCE_CREATED'
        ).first()
        assert event is not None
        body = json.loads(event.raw_body)
        assert body['preference_id'] == 'PREF-TEST-123456'

    def test_iniciar_pago_orden_no_pending_retorna_400(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        orden_pendiente.status = 'DELIVERED'
        orden_pendiente.save()
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ORDER_NOT_PAYABLE'

    def test_iniciar_pago_orden_inexistente_retorna_400(
        self, auth_client, db
    ):
        res = auth_client.post(INITIATE_URL, {
            'order_number': 'PY-NO-EXISTE',
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_iniciar_pago_gateway_down_retorna_503(
        self, auth_client, orden_pendiente, mp_gateway_activo, db
    ):
        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.preference.return_value.create.return_value = {
                'status': 400,
                'response': {'message': 'Invalid access token'},
            }
            res = auth_client.post(INITIATE_URL, {
                'order_number': orden_pendiente.order_number,
            }, format='json')
        assert res.status_code == 503
        assert res.json()['codigo_error'] == 'GATEWAY_UNAVAILABLE'

    def test_br009_credenciales_no_en_respuesta(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        """BR-009: las credenciales del gateway NUNCA deben aparecer en la respuesta."""
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')
        respuesta_str = json.dumps(res.json())
        assert 'TEST-ACCESS-TOKEN-FAKE' not in respuesta_str
        assert 'TEST-PUBLIC-KEY-FAKE'   not in respuesta_str
        assert 'access_token'           not in respuesta_str

    def test_retorno_gateway_aprobado_actualiza_payment(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        # Crear el Payment primero
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')

        return_url = f'/api/v2/payments/{orden_pendiente.order_number}/return/'
        res = auth_client.get(return_url, {
            'status': 'approved',
            'payment_id': '12345678',
        })
        # P-02: el retorno redirige (302) el navegador al storefront en vez de
        # devolver JSON; el efecto sobre el Payment se conserva.
        assert res.status_code == 302
        assert res['Location'].endswith(
            f'/order/{orden_pendiente.order_number}/confirmation'
        )
        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.status == 'APPROVED'
        assert payment.gateway_payment_id == '12345678'

    def test_retorno_gateway_pendiente_no_cambia_status(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')

        return_url = f'/api/v2/payments/{orden_pendiente.order_number}/return/'
        res = auth_client.get(return_url, {'status': 'pending'})

        # P-02: pending redirige a la página de verificación (polling), sin
        # alterar el status del Payment.
        assert res.status_code == 302
        assert res['Location'].endswith(
            f'/checkout/payment-return/{orden_pendiente.order_number}'
        )
        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.status == 'PENDING'

    def test_retorno_gateway_rechazado_redirige_a_payment_failed(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        # P-02: al rechazar la tarjeta, "Volver a la tienda" debe llevar al
        # storefront (payment-failed), no a un JSON crudo del host de la API.
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')

        return_url = f'/api/v2/payments/{orden_pendiente.order_number}/return/'
        res = auth_client.get(return_url, {'status': 'rejected'})

        assert res.status_code == 302
        assert res['Location'].endswith(
            f'/order/{orden_pendiente.order_number}/payment-failed'
        )


# =============================================================================
# UC-PAY-01-EXT — Cuotas MSI
# =============================================================================

class TestCuotasMSI:

    def test_planes_cuotas_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(INSTALLMENT_URL)
        assert res.status_code == 401

    def test_planes_cuotas_sin_order_number_retorna_400(
        self, auth_client, db
    ):
        res = auth_client.get(INSTALLMENT_URL)
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ORDER_NUMBER_REQUIRED'

    def test_planes_cuotas_retorna_solo_msi(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        """Solo planes con interest_rate = 0 (MSI)."""
        res = auth_client.get(INSTALLMENT_URL, {
            'order_number': orden_pendiente.order_number,
        })
        assert res.status_code == 200
        plans = res.json()['plans']
        for plan in plans:
            assert plan['interest_rate'] == '0.00', f"Plan con interés encontrado: {plan}"

    def test_planes_cuotas_estructura_correcta(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        res = auth_client.get(INSTALLMENT_URL, {
            'order_number': orden_pendiente.order_number,
        })
        data = res.json()
        assert 'order_number' in data
        assert 'amount' in data
        assert 'plans' in data
        if data['plans']:
            plan = data['plans'][0]
            assert 'installments' in plan
            assert 'amount_per_installment' in plan
            assert 'total_amount' in plan
            assert 'interest_rate' in plan

    def test_iniciar_pago_con_cuotas_msi(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        """UC-PAY-01-EXT: iniciar pago con 3 cuotas MSI."""
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
            'installments': 3,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['installments'] == 3
        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.installments == 3

    def test_amount_mismatch_retorna_422(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        """UC-PAY-01 AC-06: si el monto de la orden cambió entre el cálculo del
        checkout y la creación de la preferencia → HTTP 422 con
        codigo_error = AMOUNT_MISMATCH.

        Simula el drift: tras crear la orden PENDING, su OrderValue.total cambia
        (p.ej. recálculo de impuestos/envío por el cliente) antes de iniciar el
        pago. El backend detecta la divergencia y rechaza con 422.

        AC-06 implementado: InitiatePaymentSerializer acepta ``expected_amount``
        y InitiatePaymentView lo contrasta con ``order.value.total``.
        """
        # Drift del monto: el OrderValue.total cambia respecto al snapshot del
        # checkout, simulando recálculo entre el checkout y la preferencia.
        orden_pendiente.value.total = Decimal('9999.00')
        orden_pendiente.value.save(update_fields=['total'])

        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
            # AC-06: el cliente envía el monto que vio en el checkout; el backend
            # lo contrasta con el total recalculado de la orden.
            'expected_amount': '3000.00',
        }, format='json')
        assert res.status_code == 422, (
            f'Esperado 422 AMOUNT_MISMATCH (AC-06), recibido {res.status_code}: '
            f'{res.json() if hasattr(res, "json") else res.content}'
        )
        assert res.json().get('codigo_error') == 'AMOUNT_MISMATCH'


# =============================================================================
# UC-ORD-01-EXT — Checkout Express
# =============================================================================

class TestCheckoutExpress:

    def test_eligibility_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(ELIGIBILITY_URL)
        assert res.status_code == 401

    def test_primer_comprador_no_es_elegible(self, auth_client, db):
        """Sin órdenes previas entregadas → express_available: false."""
        res = auth_client.get(ELIGIBILITY_URL)
        assert res.status_code == 200
        assert res.json()['express_available'] is False

    def test_comprador_recurrente_con_direccion_es_elegible(
        self, auth_client, user, cat_s15, db
    ):
        """Comprador con orden DELIVERED y dirección default → eligible."""

        ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('80'), estimated_days=5, is_active=True
        )
        Address.objects.create(
            user=user, alias='Casa',
            recipient_name='Test', street='Calle 1',
            city='CDMX', state='CMX', zip_code='06600',
            is_default=True,
        )
        # Crear orden entregada
        o = Order.objects.create(user=user, status='DELIVERED')

        res = auth_client.get(ELIGIBILITY_URL)
        data = res.json()
        assert data['express_available'] is True
        assert data['default_address'] is not None
        assert data['default_shipping'] is not None

    def test_comprador_sin_direccion_default_no_es_elegible(
        self, auth_client, user, db
    ):
        Order.objects.create(user=user, status='DELIVERED')
        # Sin dirección default
        res = auth_client.get(ELIGIBILITY_URL)
        assert res.json()['express_available'] is False

    def test_express_checkout_sin_ser_recurrente_retorna_400(
        self, auth_client, prod_s15, db
    ):
        """Sin órdenes previas → no elegible para express checkout."""
        auth_client.post('/api/v2/cart/items/', {
            'product_id': prod_s15.pk, 'quantity': 1,
        }, format='json')
        res = auth_client.post(EXPRESS_URL, {}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'NOT_ELIGIBLE_EXPRESS'

    def test_express_checkout_crea_orden(
        self, auth_client, user, prod_s15, db
    ):
        """Comprador elegible con carrito → crea orden directa."""

        ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('80'), estimated_days=5, is_active=True
        )
        # H-API-07: el seed ya provee la zona '06' activa y zip_code_prefix es
        # UNIQUE -> get_or_create (idempotente), no create (que chocaria).
        ShippingZone.objects.get_or_create(
            zip_code_prefix='06', defaults={'name': 'CDMX', 'is_active': True})
        Address.objects.create(
            user=user, alias='Casa',
            recipient_name='Test User', street='Reforma 100',
            city='CDMX', state='CMX', zip_code='06600',
            is_default=True,
        )
        Order.objects.create(user=user, status='DELIVERED')

        # Agregar producto al carrito
        prod_s15.stock = 10
        prod_s15.save()
        auth_client.post('/api/v2/cart/items/', {
            'product_id': prod_s15.pk, 'quantity': 1,
        }, format='json')

        res = auth_client.post(EXPRESS_URL, {}, format='json')
        assert res.status_code == 201, res.json()
        data = res.json()
        assert data['order_number'].startswith('PY-')
        assert data['status'] == 'PENDING'

    def test_express_checkout_vacia_el_carrito(
        self, auth_client, user, prod_s15, db
    ):

        ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('80'), estimated_days=5, is_active=True
        )
        # H-API-07: el seed ya provee la zona '06' activa y zip_code_prefix es
        # UNIQUE -> get_or_create (idempotente), no create (que chocaria).
        ShippingZone.objects.get_or_create(
            zip_code_prefix='06', defaults={'name': 'CDMX', 'is_active': True})
        Address.objects.create(
            user=user, alias='Casa',
            recipient_name='Test', street='Calle',
            city='CDMX', state='CMX', zip_code='06600',
            is_default=True,
        )
        Order.objects.create(user=user, status='DELIVERED')

        auth_client.post('/api/v2/cart/items/', {
            'product_id': prod_s15.pk, 'quantity': 1,
        }, format='json')

        auth_client.post(EXPRESS_URL, {}, format='json')
        # S4: confirmar el draft lo transiciona — no queda draft del usuario.
        assert Order.objects.filter(user=user, status=Order.STATUS_DRAFT).count() == 0


# =============================================================================
# additional_info en la preferencia (Checkout Pro) — calidad de integracion
# =============================================================================

class TestPreferencePayerEnrichment:
    """create_preference debe enviar payer enriquecido + shipments a MP."""

    def _capture_preference(self, order):
        gw = MercadoPagoGateway.__new__(MercadoPagoGateway)
        captured = {}
        sdk = MagicMock()

        def _create(payload):
            captured['payload'] = payload
            return {
                'status': 201,
                'response': {
                    'id': 'PREF-ENRICH-1',
                    'init_point': 'https://www.mercadopago.com.mx/redirect?pref_id=PREF-ENRICH-1',
                },
            }

        sdk.preference.return_value.create.side_effect = _create
        with patch('addons.payment_mercado_pago.gateway._get_sdk', return_value=sdk):
            gw.create_preference(
                order,
                back_urls={'success': 'https://x/s', 'failure': 'https://x/f',
                           'pending': 'https://x/p'},
            )
        return captured['payload']

    def test_preference_payer_incluye_nombre(self, orden_pendiente, db):
        payer = self._capture_preference(orden_pendiente)['payer']
        assert payer['email']   # el email se conserva
        assert payer['name'] == 'Test'
        assert payer['surname'] == 'User'

    def test_preference_payer_incluye_direccion(self, orden_pendiente, db):
        payer = self._capture_preference(orden_pendiente)['payer']
        assert payer['address']['zip_code'] == '06600'
        assert payer['address']['street_name'] == 'Av. Reforma 100'

    def test_preference_incluye_shipments(self, orden_pendiente, db):
        payload = self._capture_preference(orden_pendiente)
        addr = payload['shipments']['receiver_address']
        assert addr['zip_code'] == '06600'
        assert addr['city_name'] == 'CDMX'
