"""
Tests — Gestión admin de órdenes y dashboard (UC-ORD-07..10)

Nombre descriptivo: dominio y perspectiva, no número de sprint.
"""
import pytest
from decimal import Decimal
from addons.authz.services import SUPERADMIN_ROLE_CODE
from addons.catalogue.models import Category, Product
from addons.delivery.models import Courier, ShipmentGuide
from addons.orders.admin_services import transition_order_status
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress, OrderStatusLog
from addons.payment.models import Payment
from addons.sale.models import SaleOrder
from django.contrib.auth import get_user_model
from addons.base.models import SiteSettings


def _canonical_order(user, *, approved=False):
    """Orden enlazada a una SaleOrder confirmada (ejes O2C, sin columna espejo).

    Sin pago aprobado → proyecta PENDING; con pago aprobado → PAID.
    """
    so = SaleOrder.objects.create(state=SaleOrder.STATE_SALE)
    order = Order.objects.create(user=user, sale_order=so)
    if approved:
        Payment.objects.create(
            order=order, sale_order=so,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            amount=Decimal('100.00'),
            status=Payment.STATUS_APPROVED,
        )
    return order

pytestmark = pytest.mark.integration

ADMIN_LIST_URL       = '/api/v2/admin/orders/'
ADMIN_DETAIL_URL     = lambda o: f'/api/v2/admin/orders/{o}/'
ADMIN_STATUS_URL     = lambda o: f'/api/v2/admin/orders/{o}/status/'
ADMIN_CANCEL_URL     = lambda o: f'/api/v2/admin/orders/{o}/cancellations/'
ADMIN_DASHBOARD_URL  = '/api/v2/admin/dashboard/'


@pytest.fixture
def cat_adm(db):
    return Category.objects.create(name='Cat Admin', slug='cat-adm', is_active=True)


@pytest.fixture
def prod_adm(db, cat_adm):
    _p = Product.objects.create(
        name='Elekes Admin', slug='elekes-admin', sku='ADM-001',
        description='',
        price=Decimal('900.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_adm)
    return _p


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


def _canonical_admin_order(user, prod, *, approved=False, mirror='PENDING'):
    """Orden con scaffolding de lista (``_make_order``) enlazada a una
    ``SaleOrder`` confirmada; la columna espejo se deja **stale** a propósito
    (``mirror``) para probar que el filtro deriva de los ejes, no del espejo."""
    order = _make_order(user, prod, status=mirror)
    so = SaleOrder.objects.create(state=SaleOrder.STATE_SALE)
    order.sale_order = so
    order.save(update_fields=['sale_order'])
    if approved:
        Payment.objects.create(
            order=order, sale_order=so, gateway=Payment.GATEWAY_MERCADOPAGO,
            amount=Decimal('100.00'), status=Payment.STATUS_APPROVED,
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
            email='oa@test.com', password='pass'
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

    def test_filtro_por_status_canonico_desde_ejes(
        self, admin_client, user, prod_adm, db
    ):
        """O2C R6: el ?status= admin deriva de los ejes canónicos (pago), no
        de la columna espejo. La orden pagada tiene espejo stale 'PENDING'
        pero se filtra correctamente como PAID."""
        pend = _canonical_admin_order(user, prod_adm, approved=False)
        paid = _canonical_admin_order(user, prod_adm, approved=True)  # espejo stale
        res = admin_client.get(ADMIN_LIST_URL, {'status': 'PAID'})
        nums = {o['order_number'] for o in res.json()['results']}
        assert paid.order_number in nums
        assert pend.order_number not in nums

    def test_filtro_por_status_muerto_400(
        self, admin_client, user, prod_adm, db
    ):
        """O2C R6: los valores muertos del enum legacy salen del contrato
        admin → 400 INVALID_STATUS."""
        _canonical_admin_order(user, prod_adm)
        res = admin_client.get(ADMIN_LIST_URL, {'status': 'IN_PREPARATION'})
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_STATUS'

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

    def test_admin_listado_expone_user_email_y_username(
        self, admin_client, user, prod_adm, db,
    ):
        """UC-ORD-09 D-ORD-09.01 (DEC-AOQ-02): AdminOrderSerializer
        expone user_email + user_username derivados del FK para que el
        UI admin pueda renderizar la columna 'Comprador'. Antes
        OrderSerializer base solo exponia user como PK entero."""
        _make_order(user, prod_adm, 'PENDING')
        res = admin_client.get(ADMIN_LIST_URL)
        assert res.status_code == 200
        results = res.json()['results']
        assert results, 'al menos una orden'
        first = results[0]
        assert first['user_email'] == user.email
        assert first['user_username'] == user.email


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
        courier = Courier.objects.create(name='DHL Test', code='DHL', is_active=True)

        for new_status in ['PROCESSING', 'IN_PREPARATION', 'SHIPPED', 'DELIVERED']:
            if new_status == 'SHIPPED':
                ShipmentGuide.objects.create(
                    order=order, courier=courier, tracking_number='TEST-SHIP-001',
                )
            res = admin_client.patch(
                ADMIN_STATUS_URL(order.order_number),
                {'new_status': new_status},
                format='json',
            )
            assert res.status_code == 200, f'Falló en → {new_status}: {res.json()}'

        order.refresh_from_db()
        assert order.status == 'DELIVERED'
        assert OrderStatusLog.objects.filter(order=order).count() == 4

    def test_transicion_lee_status_fresh_con_select_for_update(
        self, admin_client, user, prod_adm, db,
    ):
        """UC-ORD-07 D-ORD-07.01 (DEC-AOQ-01): demuestra que
        transition_order_status re-lee el status con
        ``select_for_update()`` y no usa la instancia stale en memoria.

        Setup simula 2 admins concurrentes: admin A tiene la orden en
        memoria con status=PENDING. Admin B cancela la orden mientras
        tanto (DB ahora CANCELLED, in-memory de A sigue PENDING).
        Sin select_for_update, A leeria su instancia stale (PENDING) y
        permitiria PENDING -> PROCESSING. Con select_for_update, A re-lee
        la DB (CANCELLED terminal) y rechaza."""
        User = get_user_model()
        # Party/authz (T-201): el admin es titular del rol superadmin
        # (el usuario detrás de admin_client). No hay is_staff nativo.
        admin = User.objects.filter(
            role_assignments__role__code=SUPERADMIN_ROLE_CODE,
        ).first()
        # Admin A obtiene la orden en PENDING.
        order_in_memory_A = _make_order(user, prod_adm, 'PENDING')
        # Admin B (simulado) cancela la orden via UPDATE directo (no
        # tocar la instancia en memoria de A).
        Order.objects.filter(pk=order_in_memory_A.pk).update(status='CANCELLED')
        # Admin A intenta transicionar a PROCESSING usando su instancia
        # stale. select_for_update fuerza re-lectura: DB.status =
        # CANCELLED (terminal) -> ValueError.
        with pytest.raises(ValueError, match='Transición no permitida'):
            transition_order_status(order_in_memory_A, 'PROCESSING', admin)


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
        # O2C V5c-2: los KPIs se derivan de los ejes canónicos, no de la
        # columna espejo. Dos ventas confirmadas sin pago aprobado proyectan
        # PENDING; una con pago aprobado proyecta PAID (activa, no pending).
        SiteSettings.get_current()

        _canonical_order(user)                  # PENDING
        _canonical_order(user)                  # PENDING
        _canonical_order(user, approved=True)   # PAID (activa)

        res    = admin_client.get(ADMIN_DASHBOARD_URL)
        counts = res.json()['order_counts']
        assert counts['pending'] >= 2
        # PROCESSING e IN_PREPARATION son valores muertos (0 escritores; la
        # proyección canónica nunca los emite) → contadores provablemente 0.
        assert counts['processing'] == 0
        assert counts['in_preparation'] == 0
        # La orden PAID cuenta como activa (ni entregada ni cancelada).
        assert counts['total_active'] >= 3

    def test_dashboard_shipped_and_active_from_axes(
        self, admin_client, user, prod_adm, db
    ):
        """Guía activa proyecta SHIPPED; columna espejo ausente."""
        SiteSettings.get_current()
        order = _canonical_order(user, approved=True)
        courier = Courier.objects.create(name='DHL', code='dhl', is_active=True)
        ShipmentGuide.objects.create(
            order=order, sale_order=order.sale_order, courier=courier,
            tracking_number='TRK-DASH-1',
        )

        counts = admin_client.get(ADMIN_DASHBOARD_URL).json()['order_counts']

        assert counts['shipped'] >= 1
        assert counts['pending'] == 0          # ya tiene guía → no pending
        assert counts['total_active'] >= 1     # enviada sigue activa

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
