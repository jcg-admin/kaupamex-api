"""
Tests — Gestión admin de órdenes y dashboard (UC-ORD-07..10)

Nombre descriptivo: dominio y perspectiva, no número de sprint.

Post-retiro del addon espejo ``orders`` (SOL-098, ``api@77bd1f0``): la venta
**es** la orden. No hay una segunda entidad (``orders.Order``) que enlazar
ni una columna espejo que dejar deliberadamente "stale" para probar que el
filtro deriva de los ejes — eso ya lo prueba trivialmente al no existir otro
eje que consultar. El helper ``_canonical_admin_order`` (que construía esa
divergencia espejo/canónica) se retiró; sus llamadores usan ``_make_order``
directo (ver nota en su definición).

``SaleOrderStatusLog`` (bitácora de transiciones) se disolvió en el chatter
(``MailThread.message_track``, H-API-102) sin API de lectura equivalente
todavía. Los tests cuyo único sujeto era esa bitácora
(``test_transicion_crea_statuslog``, ``test_admin_cancelacion_registra_statuslog``)
se retiraron; la aserción de conteo de logs dentro de
``test_flujo_completo_pending_a_delivered`` (efecto colateral, no su sujeto)
se quitó, conservando el resto del test.

``transition_order_status`` (servicio de transición concurrente con
``select_for_update``) vivía en ``orders.admin_services``, retirado sin
reemplazo importable — ``test_transicion_lee_status_fresh_con_select_for_update``
se retiró: no hay forma de reencuadrarlo sin inventar la firma de un servicio
que todavía no existe en el monolito modular.
"""
import pytest
from decimal import Decimal
from addons.catalogue.models import Category, Product
from addons.delivery.models import Courier, ShipmentGuide, DeliveryAddress
from addons.delivery.models.sale_order import set_delivery_line
from addons.payment.models import Payment
from addons.sale.models import SaleOrder, SaleOrderLine
from django.contrib.auth import get_user_model
from addons.base.models import SiteSettings
from tests.factories.order_factory import make_order


def _canonical_order(user, *, approved=False):
    """Venta confirmada (ejes O2C, sin segunda entidad que enlazar).

    Sin pago aprobado → proyecta PENDING; con pago aprobado → PAID.
    """
    return make_order(status='PAID' if approved else 'PENDING', user=user)

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
    """Venta confirmada + línea de ``prod`` + envío materializado ($80,
    misma cifra histórica) + dirección de entrega.

    Reemplaza tanto la vieja ``_make_order`` (que escribía a
    ``OrderValue``/``DeliveryAddress`` del espejo) como
    ``_canonical_admin_order`` — esta última existía sólo para dejar una
    columna espejo "stale" y probar que el filtro admin deriva de los ejes
    canónicos, no de ella. Sin espejo, esa divergencia ya no es representable
    y el helper colapsa en éste: pasar ``status='PAID'`` construye
    directamente el eje de pago aprobado que antes requería un segundo paso.
    """
    order = make_order(user=user, status=status)
    SaleOrderLine.objects.create(
        order=order, name=prod.name,
        price_unit=prod.price, product_uom_qty=1,
        product=prod,
    )
    set_delivery_line(order, Decimal('80.00'))
    DeliveryAddress.objects.create(
        sale_order=order, recipient_name='T',
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
        res   = auth_client.patch(ADMIN_STATUS_URL(order.name),
                                  {'new_status': 'PAID'}, format='json')
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
        """O2C R6: el ?status= admin deriva de los ejes canónicos (pago),
        no de una columna espejo — ya no existe una segunda columna que
        pudiera quedar desalineada."""
        pend = _make_order(user, prod_adm, status='PENDING')
        paid = _make_order(user, prod_adm, status='PAID')
        res = admin_client.get(ADMIN_LIST_URL, {'status': 'PAID'})
        nums = {o['order_number'] for o in res.json()['results']}
        assert paid.name in nums
        assert pend.name not in nums

    def test_filtro_por_status_muerto_400(
        self, admin_client, user, prod_adm, db
    ):
        """O2C R6: los valores muertos del enum legacy salen del contrato
        admin → 400 INVALID_STATUS."""
        _make_order(user, prod_adm)
        res = admin_client.get(ADMIN_LIST_URL, {'status': 'IN_PREPARATION'})
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_STATUS'

    def test_filtro_por_numero_orden_parcial(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm)
        prefix = order.name[:5]

        res = admin_client.get(ADMIN_LIST_URL, {'order_number': prefix})
        assert res.json()['count'] >= 1
        first_num = res.json()['results'][0]['order_number']
        assert prefix.upper() in first_num.upper() or order.name == first_num

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

    def test_transicion_valida_pending_a_paid(
        self, admin_client, user, prod_adm, db
    ):
        # O2C R8: PENDING → PAID es conciliación manual — el hub registra
        # un Payment APPROVED gateway=MANUAL (eje de pago) y la proyección
        # deriva PAID de él.
        order = _make_order(user, prod_adm)
        res   = admin_client.patch(
            ADMIN_STATUS_URL(order.name),
            {'new_status': 'PAID', 'notes': 'Pago verificado'},
            format='json',
        )
        assert res.status_code == 200
        assert res.json()['status'] == 'PAID'
        manual = order.payments.get()
        assert manual.gateway == Payment.GATEWAY_MANUAL
        assert manual.status == Payment.STATUS_APPROVED

    def test_transicion_invalida_retorna_400(
        self, admin_client, user, prod_adm, db
    ):
        """H-ADM-002 / O2C R7: SHIPPED sólo avanza a DELIVERED."""
        order = _make_order(user, prod_adm, 'SHIPPED')
        res   = admin_client.patch(
            ADMIN_STATUS_URL(order.name),
            {'new_status': 'PENDING'},
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
            ADMIN_STATUS_URL(order.name),
            {'new_status': 'SHIPPED'},  # intentar retroceder
            format='json',
        )
        assert res.status_code == 400

    def test_flujo_completo_pending_a_delivered(
        self, admin_client, user, prod_adm, db
    ):
        """O2C R8 — flujo feliz canónico: PENDING → PAID (hub, conciliación)
        → SHIPPED (crear la guía ES la transición, eje fulfillment) →
        DELIVERED (hub marca la guía entregada)."""
        order = _make_order(user, prod_adm)
        courier = Courier.objects.create(name='DHL Test', code='DHL', is_active=True)

        res = admin_client.patch(
            ADMIN_STATUS_URL(order.name),
            {'new_status': 'PAID'}, format='json',
        )
        assert res.status_code == 200, f'Falló en → PAID: {res.json()}'

        # SHIPPED no es transición manual del hub: la guía activa ES el eje.
        ShipmentGuide.objects.create(
            sale_order=order, courier=courier,
            tracking_number='TEST-SHIP-001',
        )

        res = admin_client.patch(
            ADMIN_STATUS_URL(order.name),
            {'new_status': 'DELIVERED'}, format='json',
        )
        assert res.status_code == 200, f'Falló en → DELIVERED: {res.json()}'
        assert res.json()['status'] == 'DELIVERED'

        # Pedir SHIPPED al hub es error explícito (eje fulfillment).
        res = admin_client.patch(
            ADMIN_STATUS_URL(order.name),
            {'new_status': 'SHIPPED'}, format='json',
        )
        assert res.status_code == 400

    # UC-ORD-07 D-ORD-07.01 (DEC-AOQ-01) —
    # ``test_transicion_lee_status_fresh_con_select_for_update`` se retiró
    # (ver docstring del módulo): llamaba a ``transition_order_status``, un
    # servicio de ``orders.admin_services`` retirado sin reemplazo
    # importable. No hay firma que reencuadrar todavía.


# =============================================================================
# UC-ORD-08 — Cancelar orden (admin)
# =============================================================================

class TestCancelarOrdenAdmin:

    def test_admin_cancela_paid(
        self, admin_client, user, prod_adm, db
    ):
        """H-ADM-005 / O2C R7: el admin puede cancelar una orden PAID
        (sin guía) — el comprador también, pero admin exige motivo."""
        # O2C R8: PAID canónico = pago aprobado (MANUAL: sin refund de
        # pasarela al cancelar); el estado es la proyección del eje.
        order = _make_order(user, prod_adm)
        Payment.objects.create(
            sale_order=order,
            gateway=Payment.GATEWAY_MANUAL,
            amount=Decimal('100.00'), status=Payment.STATUS_APPROVED,
        )
        res   = admin_client.post(
            ADMIN_CANCEL_URL(order.name),
            {'reason': 'Fraude detectado en el pedido'},
            format='json',
        )
        assert res.status_code == 200
        order.refresh_from_db()
        assert order.state == SaleOrder.STATE_CANCEL
        assert order.admin_cancelled_by is not None

    def test_motivo_obligatorio_min_10_chars(
        self, admin_client, user, prod_adm, db
    ):
        order = _make_order(user, prod_adm, 'PENDING')
        res   = admin_client.post(
            ADMIN_CANCEL_URL(order.name),
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
            ADMIN_CANCEL_URL(order.name),
            {'reason': 'Motivo de prueba suficientemente largo'},
            format='json',
        )
        assert res.status_code == 400

    def test_admin_cancelacion_restaura_stock(
        self, admin_client, user, prod_adm, db
    ):
        stock_inicial = prod_adm.stock
        order = _make_order(user, prod_adm, 'PAID')
        admin_client.post(
            ADMIN_CANCEL_URL(order.name),
            {'reason': 'Stock incorrecto reportado por almacén'},
            format='json',
        )
        prod_adm.refresh_from_db()
        assert prod_adm.stock == stock_inicial + 1

    # H-ADM cancelación (admin) —
    # ``test_admin_cancelacion_registra_statuslog`` se retiró (ver docstring
    # del módulo): su único sujeto era ``SaleOrderStatusLog``, sin reemplazo
    # consultable todavía.


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
            sale_order=order, courier=courier,
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
