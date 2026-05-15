"""
Tests de integración — Sprint 15
UC-PAY-01:     Procesar Pago con MercadoPago
UC-PAY-01-EXT: Cuotas MSI
UC-ORD-01-EXT: Checkout Express
"""
import json
import uuid
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.integration

INITIATE_URL    = '/api/v1/payments/initiate/'
INSTALLMENT_URL = '/api/v1/payments/installments/'
ELIGIBILITY_URL = '/api/v1/checkout/eligibility/'
EXPRESS_URL     = '/api/v1/checkout/express/'


# =============================================================================
# Fixtures compartidos
# =============================================================================

@pytest.fixture
def cat_s15(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Cat S15', slug='cat-s15', is_active=True)


@pytest.fixture
def prod_s15(db, cat_s15):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Prod S15', slug='prod-s15', sku='S15-001',
        description='', category=cat_s15,
        price=Decimal('1500.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def orden_pendiente(db, user, prod_s15):
    """Orden en estado PENDING con OrderValue."""
    from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
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
    from apps.settings_app.models import PaymentGateway
    gw = PaymentGateway(
        name='MercadoPago Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': 'TEST-ACCESS-TOKEN-FAKE',
        'public_key':   'TEST-PUBLIC-KEY-FAKE',
    })
    gw.save()
    return gw


@pytest.fixture
def mock_mp_sdk():
    """Mock del SDK de MercadoPago para evitar llamadas reales."""
    with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
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
        from apps.payments.models import Payment
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
        from apps.payments.models import Payment, PaymentGatewayEvent
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
        assert res.json()['codigo_error'] == 'ORDEN_NO_PAGABLE'

    def test_iniciar_pago_orden_inexistente_retorna_400(
        self, auth_client, db
    ):
        res = auth_client.post(INITIATE_URL, {
            'order_number': 'PY-NO-EXISTE',
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ORDEN_NO_ENCONTRADA'

    def test_iniciar_pago_gateway_down_retorna_503(
        self, auth_client, orden_pendiente, mp_gateway_activo, db
    ):
        with patch('apps.payments.gateways.mercadopago.mercadopago') as mock_mp:
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
        assert res.json()['codigo_error'] == 'GATEWAY_NO_DISPONIBLE'

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
        from apps.payments.models import Payment
        # Crear el Payment primero
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')

        return_url = f'/api/v1/payments/{orden_pendiente.order_number}/return/'
        res = auth_client.get(return_url, {
            'status': 'approved',
            'payment_id': '12345678',
        })
        assert res.status_code == 200
        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.status == 'APPROVED'
        assert payment.gateway_payment_id == '12345678'

    def test_retorno_gateway_pendiente_no_cambia_status(
        self, auth_client, orden_pendiente, mp_gateway_activo, mock_mp_sdk, db
    ):
        from apps.payments.models import Payment
        auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
        }, format='json')

        return_url = f'/api/v1/payments/{orden_pendiente.order_number}/return/'
        auth_client.get(return_url, {'status': 'pending'})

        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.status == 'PENDING'


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
        assert res.json()['codigo_error'] == 'ORDER_NUMBER_REQUERIDO'

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
        from apps.payments.models import Payment
        res = auth_client.post(INITIATE_URL, {
            'order_number': orden_pendiente.order_number,
            'installments': 3,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['installments'] == 3
        payment = Payment.objects.get(order=orden_pendiente)
        assert payment.installments == 3


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
        from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress
        from apps.users.models import Address
        from apps.settings_app.models import ShippingMethod

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
        from apps.orders.models import Order
        Order.objects.create(user=user, status='DELIVERED')
        # Sin dirección default
        res = auth_client.get(ELIGIBILITY_URL)
        assert res.json()['express_available'] is False

    def test_express_checkout_sin_ser_recurrente_retorna_400(
        self, auth_client, prod_s15, db
    ):
        """Sin órdenes previas → no elegible para express checkout."""
        auth_client.post('/api/v1/cart/items/', {
            'product_id': prod_s15.pk, 'quantity': 1,
        }, format='json')
        res = auth_client.post(EXPRESS_URL, {}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'NO_ELEGIBLE_EXPRESS'

    def test_express_checkout_crea_orden(
        self, auth_client, user, prod_s15, db
    ):
        """Comprador elegible con carrito → crea orden directa."""
        from apps.orders.models import Order
        from apps.users.models import Address
        from apps.settings_app.models import ShippingMethod

        ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('80'), estimated_days=5, is_active=True
        )
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
        auth_client.post('/api/v1/cart/items/', {
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
        from apps.orders.models import Order
        from apps.users.models import Address
        from apps.settings_app.models import ShippingMethod
        from apps.cart.models import CartItem

        ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('80'), estimated_days=5, is_active=True
        )
        Address.objects.create(
            user=user, alias='Casa',
            recipient_name='Test', street='Calle',
            city='CDMX', state='CMX', zip_code='06600',
            is_default=True,
        )
        Order.objects.create(user=user, status='DELIVERED')

        auth_client.post('/api/v1/cart/items/', {
            'product_id': prod_s15.pk, 'quantity': 1,
        }, format='json')

        auth_client.post(EXPRESS_URL, {}, format='json')
        assert CartItem.objects.filter(product=prod_s15).count() == 0
