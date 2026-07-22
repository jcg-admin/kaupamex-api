"""
Tests — Gestión de órdenes del comprador (UC-ORD-02..06)

Nombre descriptivo: dominio, no número de sprint.
"""
import pytest
from decimal import Decimal
from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from django.contrib.auth import get_user_model
from tests.factories.user_factory import make_buyer
from addons.payment.models import Payment, Refund
from addons.settings_app.models import PaymentGateway, ShippingMethod
from unittest.mock import patch, MagicMock
from addons.chartsize.models import VariantType, VariantOption, ProductVariant

pytestmark = pytest.mark.integration

ORDERS_URL  = '/api/v2/orders/'
DETAIL_URL  = lambda o: f'/api/v2/orders/{o}/'
CANCEL_URL  = lambda o: f'/api/v2/orders/{o}/cancellations/'
ADDRESS_URL = lambda o: f'/api/v2/orders/{o}/shipping-address/'
SHIPPING_URL= lambda o: f'/api/v2/orders/{o}/shipping-method/'


# ─── Enforcement capacidad-dirigido (ADR-020, DEC-ENF-01: account.orders) ───
class TestOrdersCapabilityGate:
    """La gestión de pedidos propios (historial, detalle, cancelar, editar
    dirección/envío) exige ``account.orders`` además de autenticación. Un
    usuario autenticado SIN esa capacidad recibe 403. El POST de checkout
    (crear orden) NO se gatea — sigue AllowAny (guest checkout, DEC-ENF-03)."""

    def _authed_without_capability(self, api_client):
        u = get_user_model().objects.create_user(
            email='norole-orders@practicayoruba.mx', password='TestPass123!',
        )
        api_client.force_login(u)
        return u

    def test_history_requires_account_orders(self, api_client, db):
        self._authed_without_capability(api_client)
        assert api_client.get(ORDERS_URL).status_code == 403

    def test_detail_requires_account_orders(self, api_client, db):
        self._authed_without_capability(api_client)
        assert api_client.get(DETAIL_URL('PY-2026-000999')).status_code == 403

    def test_cancel_requires_account_orders(self, api_client, db):
        self._authed_without_capability(api_client)
        assert api_client.post(CANCEL_URL('PY-2026-000999')).status_code == 403

    def test_checkout_post_stays_public(self, api_client, db):
        # El POST de checkout NO exige account.orders (guest checkout).
        # Sin carrito válido responde 4xx de negocio, pero NUNCA 403 de capacidad.
        res = api_client.post(ORDERS_URL, {}, format='json')
        assert res.status_code != 403


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def cat_ord(db):
    return Category.objects.create(name='Cat Ord', slug='cat-ord', is_active=True)


@pytest.fixture
def prod_ord(db, cat_ord):
    _p = Product.objects.create(
        name='Collar Yoruba Test', slug='collar-yoruba-test', sku='ORD-CY-001',
        description='',
        price=Decimal('1500.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_ord)
    return _p


def _create_full_order(user, prod, status='PENDING', n_items=1):
    order = Order.objects.create(user=user, status=status)
    for i in range(n_items):
        OrderItem.objects.create(
            order=order, product_name=prod.name, sku=f'{prod.sku}-{i}',
            unit_price=prod.price, quantity=1, subtotal=prod.price,
            product=prod,
        )
    OrderValue.objects.create(
        order=order,
        subtotal=prod.price * n_items,
        tax=(prod.price * n_items * Decimal('0.16') / Decimal('1.16')).quantize(Decimal('0.01')),
        shipping_cost=Decimal('80.00'),
        discount=Decimal('0.00'),
        total=prod.price * n_items + Decimal('80.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Test User',
        street='Av. Reforma 100', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


# =============================================================================
# UC-ORD-02 — Detalle de orden
# =============================================================================

class TestDetalleOrden:

    def test_detalle_propio_retorna_200(self, auth_client, user, prod_ord, db):
        order = _create_full_order(user, prod_ord)
        res = auth_client.get(DETAIL_URL(order.order_number))
        assert res.status_code == 200
        data = res.json()
        assert data['order_number'] == order.order_number
        assert 'items' in data
        assert 'value' in data
        assert 'address' in data
        assert 'status_display' in data

    def test_rnf_sec_003_orden_ajena_retorna_404(self, auth_client, prod_ord, db):
        User = get_user_model()
        other = User.objects.create_user(
            email='other@ord.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.get(DETAIL_URL(order.order_number))
        assert res.status_code == 404  # nunca 403 — RNF-SEC-003
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_detalle_incluye_snapshots_br005(self, auth_client, user, prod_ord, db):
        """BR-005: el precio del item es el del checkout, no el actual."""
        order = _create_full_order(user, prod_ord)
        # Cambiar precio del producto
        prod_ord.price = Decimal('9999.00')
        prod_ord.save()

        res = auth_client.get(DETAIL_URL(order.order_number))
        item = res.json()['items'][0]
        assert Decimal(item['unit_price']) == Decimal('1500.00')  # precio original

    def test_detalle_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(DETAIL_URL('PY-GHOST'))
        assert res.status_code == 401


# =============================================================================
# UC-ORD-03 — Listado paginado
# =============================================================================

class TestListadoOrdenes:

    def test_listado_solo_muestra_ordenes_propias(
        self, auth_client, user, prod_ord, db
    ):
        User = get_user_model()
        other = User.objects.create_user(
            email='ol@test.com', password='pass'
        )
        _create_full_order(user, prod_ord)
        _create_full_order(user, prod_ord)
        _create_full_order(other, prod_ord)   # no debe aparecer

        res = auth_client.get(ORDERS_URL)
        assert res.status_code == 200
        assert res.json()['count'] == 2

    def test_listado_paginado_10_por_pagina(
        self, auth_client, user, prod_ord, db
    ):
        for _ in range(12):
            _create_full_order(user, prod_ord)

        res = auth_client.get(ORDERS_URL)
        assert len(res.json()['results']) == 10
        assert res.json()['count'] == 12

    def test_listado_ordenado_por_created_desc(
        self, auth_client, user, prod_ord, db
    ):
        o1 = _create_full_order(user, prod_ord, status='PENDING')
        o2 = _create_full_order(user, prod_ord, status='DELIVERED')

        res = auth_client.get(ORDERS_URL)
        results = res.json()['results']
        # El más reciente primero (por created_at DESC)
        assert results[0]['order_number'] == o2.order_number

    def test_listado_filtro_status(
        self, auth_client, user, prod_ord, db,
    ):
        """UC-ORD-03 D-08 (DEC-ORD-07): filtro por ?status."""
        _create_full_order(user, prod_ord, status='PENDING')
        o_delivered = _create_full_order(user, prod_ord, status='DELIVERED')
        res = auth_client.get(f'{ORDERS_URL}?status=DELIVERED')
        assert res.status_code == 200
        results = res.json()['results']
        assert len(results) == 1
        assert results[0]['order_number'] == o_delivered.order_number

    def test_listado_filtro_status_invalido_400(
        self, auth_client, user, prod_ord, db,
    ):
        """UC-ORD-03 D-08: status invalido -> 400 INVALID_STATUS."""
        _create_full_order(user, prod_ord, status='PENDING')
        res = auth_client.get(f'{ORDERS_URL}?status=UNICORN')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_STATUS'

    def test_listado_incluye_campos_requeridos(
        self, auth_client, user, prod_ord, db
    ):
        _create_full_order(user, prod_ord)
        res = auth_client.get(ORDERS_URL)
        item = res.json()['results'][0]
        required = {'order_number', 'status', 'status_display',
                    'created_at', 'total', 'items_count'}
        assert required.issubset(set(item.keys()))


# =============================================================================
# UC-ORD-04 — Cancelar orden
# =============================================================================

class TestCancelarOrden:

    def test_cancelar_orden_pending(self, auth_client, user, prod_ord, db):
        order = _create_full_order(user, prod_ord, status='PENDING')
        res = auth_client.post(CANCEL_URL(order.order_number),
                               {'reason': 'Me arrepentí'}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CANCELLED'
        order.refresh_from_db()
        assert order.cancellation_reason == 'Me arrepentí'
        assert order.cancelled_at is not None

    def test_cancelar_orden_processing(self, auth_client, user, prod_ord, db):
        """H-ORD-002: PROCESSING = PAYMENT_CONFIRMED de la FR — cancelable."""
        order = _create_full_order(user, prod_ord, status='PROCESSING')
        res = auth_client.post(CANCEL_URL(order.order_number), {}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CANCELLED'

    def test_cancelar_restaura_stock(self, auth_client, user, prod_ord, db):
        stock_inicial = prod_ord.stock
        order = _create_full_order(user, prod_ord, status='PENDING')
        auth_client.post(CANCEL_URL(order.order_number), {}, format='json')
        prod_ord.refresh_from_db()
        assert prod_ord.stock == stock_inicial + 1

    def test_cancelar_in_preparation_no_permitido(
        self, auth_client, user, prod_ord, db
    ):
        """IN_PREPARATION no es cancelable por el comprador."""
        order = _create_full_order(user, prod_ord, status='IN_PREPARATION')
        res = auth_client.post(CANCEL_URL(order.order_number), {}, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'CANCELLATION_NOT_ALLOWED'

    def test_cancelar_delivered_no_permitido(
        self, auth_client, user, prod_ord, db
    ):
        order = _create_full_order(user, prod_ord, status='DELIVERED')
        res = auth_client.post(CANCEL_URL(order.order_number), {}, format='json')
        assert res.status_code == 400

    def test_cancelacion_con_pago_inicia_reembolso(
        self, auth_client, user, prod_ord, db
    ):
        """H-ORD-004: cancelar orden PROCESSING con Payment → reembolso automático."""

        gw = PaymentGateway(name='MP', gateway='MERCADOPAGO', is_active=True)
        gw.set_credentials({'access_token': 'T', 'client_secret': 'S'})
        gw.save()

        order = _create_full_order(user, prod_ord, status='PROCESSING')
        payment = Payment.objects.create(
            order=order, gateway='MERCADOPAGO',
            gateway_payment_id='MP-CANCEL-001',
            preference_id='PREF-CANCEL',
            status='APPROVED', amount=prod_ord.price + Decimal('80'),
        )

        with patch('addons.payment_mercado_pago.gateway.mercadopago') as mock_mp:
            sdk = MagicMock()
            mock_mp.SDK.return_value = sdk
            sdk.refund.return_value.create.return_value = {
                'status': 201,
                'response': {'id': 777, 'amount': float(payment.amount), 'status': 'approved'},
            }
            res = auth_client.post(
                CANCEL_URL(order.order_number),
                {'reason': 'Cancelación con reembolso'},
                format='json',
            )

        assert res.status_code == 200
        payment.refresh_from_db()
        assert payment.status == 'REFUNDED'
        assert Refund.objects.filter(payment=payment).exists()

    def test_cancelar_orden_pagada(self, auth_client, user, prod_ord, db):
        """H-ORD-S01 regression: orden en estado PAID es cancelable por el comprador.

        PAID = pago confirmado por webhook pero aún no en preparación.
        Debe incluirse en CANCELABLE_STATUSES para evitar que el comprador
        quede atrapado con una orden pagada que no puede cancelar.
        """
        order = _create_full_order(user, prod_ord, status='PAID')
        res = auth_client.post(
            CANCEL_URL(order.order_number),
            {'reason': 'Cambié de opinión'},
            format='json',
        )
        assert res.status_code == 200, res.json()
        assert res.json()['status'] == 'CANCELLED'
        order.refresh_from_db()
        assert order.status == 'CANCELLED'
        assert order.cancellation_reason == 'Cambié de opinión'
        assert order.cancelled_at is not None

    def test_cancelar_rnf_sec_003_orden_ajena_retorna_404(
        self, auth_client, prod_ord, db
    ):
        User = get_user_model()
        other = User.objects.create_user(
            email='oc@test.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.post(CANCEL_URL(order.order_number), {}, format='json')
        assert res.status_code == 404


# =============================================================================
# UC-ORD-05 — Editar dirección
# =============================================================================

class TestEditarDireccion:

    def test_editar_direccion_orden_pending(self, auth_client, user, prod_ord, db):
        order = _create_full_order(user, prod_ord, status='PENDING')
        res = auth_client.patch(ADDRESS_URL(order.order_number), {
            'recipient_name': 'Nuevo Destinatario',
            'street':         'Calle Nueva 999',
            'city':           'Guadalajara',
            'state':          'Jalisco',
            'zip_code':       '44100',
        }, format='json')
        assert res.status_code == 200
        order.refresh_from_db()
        assert order.address.city == 'Guadalajara'

    def test_editar_direccion_in_preparation_permitido(
        self, auth_client, user, prod_ord, db
    ):
        """IN_PREPARATION: aún no hay guía — edición permitida."""
        order = _create_full_order(user, prod_ord, status='IN_PREPARATION')
        res = auth_client.patch(ADDRESS_URL(order.order_number), {
            'recipient_name': 'Prueba', 'street': 'St 1',
            'city': 'MTY', 'state': 'NL', 'zip_code': '64000',
        }, format='json')
        assert res.status_code == 200

    def test_editar_direccion_shipped_no_permitido(
        self, auth_client, user, prod_ord, db
    ):
        order = _create_full_order(user, prod_ord, status='SHIPPED')
        res = auth_client.patch(ADDRESS_URL(order.order_number), {
            'recipient_name': 'X', 'street': 'Y',
            'city': 'Z', 'state': 'W', 'zip_code': '00000',
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'ADDRESS_NOT_EDITABLE'

    def test_editar_direccion_rnf_sec_003(self, auth_client, prod_ord, db):
        User = get_user_model()
        other = User.objects.create_user(
            email='oa@test.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.patch(ADDRESS_URL(order.order_number), {
            'recipient_name': 'X', 'street': 'Y',
            'city': 'Z', 'state': 'W', 'zip_code': '00000',
        }, format='json')
        assert res.status_code == 404

    def test_editar_direccion_registra_auditoria(
        self, auth_client, user, prod_ord, db
    ):
        """H-API-05 (T-005/ORD-05): cada edición de dirección deja un
        OrderStatusLog — antes update_order_address solo hacía logger.info,
        sin ningún rastro auditable en la orden."""
        order = _create_full_order(user, prod_ord, status='PENDING')
        logs_before = order.status_logs.count()

        res = auth_client.patch(ADDRESS_URL(order.order_number), {
            'recipient_name': 'Nuevo Destinatario',
            'street':         'Calle Nueva 999',
            'city':           'Guadalajara',
            'state':          'Jalisco',
            'zip_code':       '44100',
        }, format='json')

        assert res.status_code == 200
        assert order.status_logs.count() == logs_before + 1
        log = order.status_logs.order_by('-created_at').first()
        assert log.changed_by_id == user.id
        # No hay transición de estado real — se usa el mismo patrón de
        # OrderStatusLog que cancel_order, sin cambiar Order.status.
        assert log.previous_status == log.new_status == order.status
        assert 'Guadalajara' in log.notes


# =============================================================================
# UC-ORD-06 — Cambiar método de envío
# =============================================================================

class TestCambiarMetodoEnvio:

    @pytest.fixture
    def shipping_methods(self, db):
        express = ShippingMethod.objects.create(
            name='Express', cost=Decimal('150.00'),
            estimated_days=1, is_active=True,
        )
        standard = ShippingMethod.objects.create(
            name='Estándar', cost=Decimal('50.00'),
            estimated_days=5, is_active=True,
        )
        return {'express': express, 'standard': standard}

    def test_cambiar_envio_recalcula_total(
        self, auth_client, user, prod_ord, shipping_methods, db
    ):

        order = _create_full_order(user, prod_ord, status='PENDING')
        order.shipping_method = shipping_methods['express']
        order.value.shipping_cost = Decimal('150.00')
        order.value.total = prod_ord.price + Decimal('150.00')
        order.shipping_method.save()
        order.value.save()
        order.save()

        res = auth_client.patch(SHIPPING_URL(order.order_number), {
            'shipping_method_id': shipping_methods['standard'].pk,
        }, format='json')

        assert res.status_code == 200
        order.refresh_from_db()
        # H-ORD-007: total = neto + tax + nuevo_shipping
        neto = order.value.subtotal - order.value.discount
        expected_total = neto + order.value.tax + Decimal('50.00')
        assert order.value.total == expected_total

    def test_cambiar_envio_shipped_no_permitido(
        self, auth_client, user, prod_ord, shipping_methods, db
    ):
        """UC-ORD-06 PARTE 7.3 (DEC-ORD-04): orden en estado no-editable
        -> 409 ORDER_NOT_EDITABLE (antes 400 METHOD_NOT_EDITABLE)."""
        order = _create_full_order(user, prod_ord, status='SHIPPED')
        res = auth_client.patch(SHIPPING_URL(order.order_number), {
            'shipping_method_id': shipping_methods['standard'].pk,
        }, format='json')
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'ORDER_NOT_EDITABLE'

    def test_cambiar_envio_pagada_no_permitido(
        self, auth_client, user, prod_ord, shipping_methods, db
    ):
        """D-3 (UC-ORD-06 v2.2.0): cambiar el método de envío en una orden
        ya PAGADA recalcularía el total sin conciliar el pago capturado
        (cobro/reembolso no implementado) -> se rechaza con 409
        ORDER_NOT_EDITABLE. El cambio solo se permite en estados pre-pago
        (PENDING/PROCESSING)."""
        for paid_status in ('PAID', 'IN_PREPARATION'):
            order = _create_full_order(user, prod_ord, status=paid_status)
            res = auth_client.patch(SHIPPING_URL(order.order_number), {
                'shipping_method_id': shipping_methods['standard'].pk,
            }, format='json')
            assert res.status_code == 409, paid_status
            assert res.json()['codigo_error'] == 'ORDER_NOT_EDITABLE', paid_status

    def test_cambiar_envio_inexistente_retorna_400(
        self, auth_client, user, prod_ord, db
    ):
        """UC-ORD-06 PARTE 7.3 (DEC-ORD-04): shipping_method invalido
        -> 400 SHIPPING_METHOD_NOT_AVAILABLE."""
        order = _create_full_order(user, prod_ord, status='PENDING')
        res = auth_client.patch(SHIPPING_URL(order.order_number), {
            'shipping_method_id': 99999,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'SHIPPING_METHOD_NOT_AVAILABLE'

    def test_cambiar_envio_registra_auditoria(
        self, auth_client, user, prod_ord, shipping_methods, db
    ):
        """H-API-06 (T-007-audit/ORD-06): cada cambio de método de envío
        deja un OrderStatusLog — antes update_shipping_method solo hacía
        logger.info, sin ningún rastro auditable en la orden. D-3 resuelto:
        el cambio solo se permite pre-pago (aquí PENDING), donde el recálculo
        del total precede a la captura del pago (sin conciliación pendiente)."""
        order = _create_full_order(user, prod_ord, status='PENDING')
        order.shipping_method = shipping_methods['express']
        order.shipping_method.save()
        order.save()
        logs_before = order.status_logs.count()

        res = auth_client.patch(SHIPPING_URL(order.order_number), {
            'shipping_method_id': shipping_methods['standard'].pk,
        }, format='json')

        assert res.status_code == 200
        assert order.status_logs.count() == logs_before + 1
        log = order.status_logs.order_by('-created_at').first()
        assert log.changed_by_id == user.id
        # No hay transición de estado real — se usa el mismo patrón de
        # OrderStatusLog que cancel_order, sin cambiar Order.status.
        assert log.previous_status == log.new_status == order.status
        assert shipping_methods['standard'].name in log.notes


# =============================================================================
# VARIANTE_CON_ORDENES — H-ORD-005
# =============================================================================

class TestProteccionVariantesOrdenes:

    def test_no_eliminar_variante_con_orden_activa(self, admin_client, prod_ord, db):
        """H-ORD-005: variante con ActiveOrder no puede eliminarse."""
        User = get_user_model()

        vtype  = VariantType.objects.create(name='Talla', product=prod_ord)
        vopt   = VariantOption.objects.create(
            variant_type=vtype, label='M', slug='m'
        )
        variant = ProductVariant.objects.create(
            product=prod_ord, option=vopt, sku_suffix='M',
            price_override=Decimal('1500'), stock=5, is_active=True,
        )

        user = User.objects.create_user(
            email='bv@test.com', password='pass'
        )
        order = Order.objects.create(user=user, status='PENDING')
        OrderItem.objects.create(
            order=order, product_name=prod_ord.name, sku=prod_ord.sku + '-M',
            unit_price=variant.price_override if variant.price_override else prod_ord.price, quantity=1,
            subtotal=variant.price_override if variant.price_override else prod_ord.price,
            variant=variant, product=prod_ord,
        )
        OrderValue.objects.create(
            order=order, subtotal=Decimal('1500'), tax=Decimal('200'),
            shipping_cost=Decimal('80'), discount=Decimal('0'),
            total=Decimal('1500') + Decimal('280'),
        )
        OrderAddress.objects.create(
            order=order, recipient_name='T', street='S',
            city='CDMX', state='CMX', zip_code='06600',
        )

        res = admin_client.delete(f'/api/v2/admin/products/{prod_ord.pk}/variants/{variant.pk}/')
        assert res.status_code == 400
