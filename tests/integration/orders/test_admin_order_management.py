"""
Tests — Gestión admin de órdenes y dashboard (UC-ORD-07..10)

Nombre descriptivo: dominio y perspectiva, no número de sprint.
"""
import pytest
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderItem, OrderValue, OrderAddress, OrderStatusLog
from django.contrib.auth import get_user_model
from apps.settings_app.models import SiteSettings

pytestmark = pytest.mark.integration

ADMIN_LIST_URL       = '/api/v1/admin/orders/'
ADMIN_DETAIL_URL     = lambda o: f'/api/v1/admin/orders/{o}/'
ADMIN_STATUS_URL     = lambda o: f'/api/v1/admin/orders/{o}/status/'
ADMIN_CANCEL_URL     = lambda o: f'/api/v1/admin/orders/{o}/cancel/'
ADMIN_DASHBOARD_URL  = '/api/v1/admin/dashboard/'


@pytest.fixture
def cat_adm(db):
    return Category.objects.create(name='Cat Admin', slug='cat-adm', is_active=True)


@pytest.fixture
def prod_adm(db, cat_adm):
    return Product.objects.create(
        name='Elekes Admin', slug='elekes-admin', sku='ADM-001',
        description='', category=cat_adm,
        price=Decimal('900.00'), stock=10,
        is_active=True, is_published=True,
    )


def _make_order(user, prod, status='PENDING'):
    order = Order.objects.create(user=user, status=status)
    OrderItem.objects.create(
        order=order, product_name=prod.name, sku=prod.sku,
        unit_price=prod.price, quantity=1, subtotal=prod.price,
        product=prod,
    )
    OrderValue.objects.create(
        order=order, subtotal=prod.price,
        tax=(prod.price * Decimal('0.16') / Decimal('1.16')).quantize(Decimal('0.01')),
        shipping_cost=Decimal('80'), discount=Decimal('0'),
        total=prod.price + Decimal('80'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='T',
        street='S 1', city='CDMX', state='CMX', zip_code='06600',
    )
    return order


# =============================================================================
# Seguridad — solo admins pueden acceder
# =============================================================================

class TestSeguridadAdminEndpoints:

    def test_usuario_normal_no_accede_a_lista_admin(self, user, auth_client, db):
        res = auth_client.get(ADMIN_LIST_URL)
        assert res.status_code == 403

    def test_usuario_normal_no_puede_cambiar_estado(
        self, auth_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm)
        res   = auth_client.patch(ADMIN_STATUS_URL(order.order_number),
                                  {'new_status': 'PROCESSING'}, format='json')
        assert res.status_code == 403

    def test_sin_auth_retorna_401(self, user, api_client, db):
        res = api_client.get(ADMIN_LIST_URL)
        assert res.status_code == 401


# =============================================================================
# UC-ORD-09 — Buscar/filtrar órdenes
# =============================================================================

class TestBuscarOrdenesAdmin:

    def test_admin_ve_todas_las_ordenes(
        self, admin_client, user, prod_adm, db
    ):
        User = get_user_model()
        other = User.objects.create_user(
            username='other_adm', email='oa@test.com', password='pass'
        )
        _make_order(user, prod_adm)
        _make_order(other,     prod_adm)

        res = admin_client.get(ADMIN_LIST_URL)
        assert res.status_code == 200
        assert res.json()['count'] >= 2

    def test_filtro_por_status(self, admin_client, user, prod_adm, db):
        _make_order(user, prod_adm, 'PENDING')
        _make_order(user, prod_adm, 'SHIPPED')

        res = admin_client.get(ADMIN_LIST_URL, {'status': 'PENDING'})
        data = res.json()
        statuses = {o['status'] for o in data['results']}
        assert statuses == {'PENDING'}

    def test_filtro_por_numero_orden_parcial(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm)
        prefix = order.order_number[:5]

        res = admin_client.get(ADMIN_LIST_URL, {'order_number': prefix})
        assert res.json()['count'] >= 1
        first_num = res.json()['results'][0]['order_number']
        assert prefix.upper() in first_num.upper() or order.order_number == first_num

    def test_filtros_combinados_and(self, admin_client, user, prod_adm, db):
        order_p = _make_order(user, prod_adm, 'PENDING')
        order_s = _make_order(user, prod_adm, 'SHIPPED')

        res = admin_client.get(ADMIN_LIST_URL, {
            'status': 'PENDING',
            'email':  user.email,
        })
        results = res.json()['results']
        statuses = {o['status'] for o in results}
        assert 'SHIPPED' not in statuses


# =============================================================================
# UC-ORD-07 — Transición de estado
# =============================================================================

class TestTransicionEstadoAdmin:

    def test_transicion_valida_pending_a_processing(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm, 'PENDING')
        res   = admin_client.patch(
            ADMIN_STATUS_URL(order.order_number),
            {'new_status': 'PROCESSING', 'notes': 'Pago verificado'},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['status'] == 'PROCESSING'

    def test_transicion_crea_statuslog(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm, 'PROCESSING')
        admin_client.patch(
            ADMIN_STATUS_URL(order.order_number),
            {'new_status': 'IN_PREPARATION'},
            format='json',
        )
        log = OrderStatusLog.objects.filter(order=order).first()
        assert log is not None
        assert log.previous_status == 'PROCESSING'
        assert log.new_status == 'IN_PREPARATION'

    def test_transicion_invalida_retorna_400(
        self, admin_client, user, prod_adm, db
    ):
        """H-ADM-002: SHIPPED no puede volver a PROCESSING."""
        order = _make_order(user, prod_adm, 'SHIPPED')
        res   = admin_client.patch(
            ADMIN_STATUS_URL(order.order_number),
            {'new_status': 'PROCESSING'},
            format='json',
        )
        assert res.status_code == 400
        # Canon EN (canon-idioma-enums-error-codes): codigo retorna EN.
        assert res.json()['codigo_error'] == 'TRANSITION_NOT_ALLOWED'

    def test_estado_terminal_no_tiene_transiciones(
        self, admin_client, user, prod_adm, db
    ):
        """DELIVERED es terminal — no hay transición posible."""
        order = _make_order(user, prod_adm, 'DELIVERED')
        res   = admin_client.patch(
            ADMIN_STATUS_URL(order.order_number),
            {'new_status': 'SHIPPED'},  # intentar retroceder
            format='json',
        )
        assert res.status_code == 400

    def test_flujo_completo_pending_a_delivered(
        self, admin_client, user, prod_adm, db
    ):
        """Flujo feliz completo: PENDING → PROCESSING → IN_PREPARATION → SHIPPED → DELIVERED."""
        order = _make_order(user, prod_adm, 'PENDING')

        for new_status in ['PROCESSING', 'IN_PREPARATION', 'SHIPPED', 'DELIVERED']:
            res = admin_client.patch(
                ADMIN_STATUS_URL(order.order_number),
                {'new_status': new_status},
                format='json',
            )
            assert res.status_code == 200, f'Falló en → {new_status}: {res.json()}'

        order.refresh_from_db()
        assert order.status == 'DELIVERED'
        assert OrderStatusLog.objects.filter(order=order).count() == 4


# =============================================================================
# UC-ORD-08 — Cancelar orden (admin)
# =============================================================================

class TestCancelarOrdenAdmin:

    def test_admin_cancela_in_preparation(
        self, admin_client, user, prod_adm, db
    ):
        """H-ADM-005: el admin puede cancelar IN_PREPARATION (el comprador no)."""
        order = _make_order(user, prod_adm, 'IN_PREPARATION')
        res   = admin_client.post(
            ADMIN_CANCEL_URL(order.order_number),
            {'reason': 'Fraude detectado en el pedido'},
            format='json',
        )
        assert res.status_code == 200
        order.refresh_from_db()
        assert order.status == 'CANCELLED'
        assert order.admin_cancelled_by is not None

    def test_motivo_obligatorio_min_10_chars(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm, 'PENDING')
        res   = admin_client.post(
            ADMIN_CANCEL_URL(order.order_number),
            {'reason': 'corto'},
            format='json',
        )
        assert res.status_code == 400
        # Canon EN (canon-idioma-enums-error-codes): codigo retorna EN.
        assert res.json()['codigo_error'] == 'CANCELLATION_NOT_ALLOWED'

    def test_admin_no_puede_cancelar_shipped(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm, 'SHIPPED')
        res   = admin_client.post(
            ADMIN_CANCEL_URL(order.order_number),
            {'reason': 'Motivo de prueba suficientemente largo'},
            format='json',
        )
        assert res.status_code == 400

    def test_admin_cancelacion_restaura_stock(
        self, admin_client, user, prod_adm, db
    ):
        stock_inicial = prod_adm.stock
        order = _make_order(user, prod_adm, 'IN_PREPARATION')
        admin_client.post(
            ADMIN_CANCEL_URL(order.order_number),
            {'reason': 'Stock incorrecto reportado por almacén'},
            format='json',
        )
        prod_adm.refresh_from_db()
        assert prod_adm.stock == stock_inicial + 1

    def test_admin_cancelacion_registra_statuslog(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm, 'PROCESSING')
        admin_client.post(
            ADMIN_CANCEL_URL(order.order_number),
            {'reason': 'Cancelación administrativa por validación'},
            format='json',
        )
        log = OrderStatusLog.objects.filter(
            order=order, new_status='CANCELLED'
        ).first()
        assert log is not None
        assert '[ADMIN]' in log.notes


# =============================================================================
# UC-ORD-10 — Dashboard transaccional
# =============================================================================

class TestDashboardTransaccional:

    def test_dashboard_retorna_cuatro_bloques(
        self, admin_client, db
    ):
        SiteSettings.get_current()  # crear singleton con defaults

        res = admin_client.get(ADMIN_DASHBOARD_URL)
        assert res.status_code == 200
        data = res.json()
        assert 'order_counts'    in data
        assert 'expiring_orders' in data
        assert 'day_summary'     in data
        assert 'latest_orders'   in data
        assert 'generated_at'    in data

    def test_dashboard_contadores_correctos(
        self, admin_client, user, prod_adm, db
    ):
        SiteSettings.get_current()

        _make_order(user, prod_adm, 'PENDING')
        _make_order(user, prod_adm, 'PENDING')
        _make_order(user, prod_adm, 'PROCESSING')

        res    = admin_client.get(ADMIN_DASHBOARD_URL)
        counts = res.json()['order_counts']
        assert counts['pending']    >= 2
        assert counts['processing'] >= 1

    def test_dashboard_sin_auth_retorna_401(self, api_client, db):
        res = api_client.get(ADMIN_DASHBOARD_URL)
        assert res.status_code == 401

    def test_dashboard_usuario_normal_retorna_403(self, auth_client, db):
        res = auth_client.get(ADMIN_DASHBOARD_URL)
        assert res.status_code == 403

    def test_sitesettings_payment_timeout_en_dashboard(
        self, admin_client, db
    ):
        """H-ADM-004: el dashboard expone el timeout configurado."""
        settings = SiteSettings.get_current()
        settings.payment_timeout_minutes = 45
        settings.save()

        res = admin_client.get(ADMIN_DASHBOARD_URL)
        assert res.json()['payment_timeout_minutes'] == 45
