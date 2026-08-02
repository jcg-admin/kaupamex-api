"""
Tests — Gestión admin de órdenes (UC-ORD-07, UC-ORD-09)

Nombre descriptivo: dominio y perspectiva, no número de sprint.

Post-retiro del addon espejo ``orders`` (SOL-098, ``api@77bd1f0``): la venta
**es** la orden. No hay una segunda entidad (``orders.Order``) que enlazar
ni una columna espejo que dejar deliberadamente "stale" para probar que el
filtro deriva de los ejes — eso ya lo prueba trivialmente al no existir otro
eje que consultar.

**Retiro parcial (H-API, este pase).** Sólo ``GET /api/v2/admin/orders/`` y
``GET /api/v2/admin/orders/<order_number>/`` existen
(``src/addons/sale_management/admin_urls.py``); su propio docstring lo dice:
*"Lo que no se restaura aquí, y por qué. El espejo también exponía una
transición de estado admin (PATCH .../status/) y un dashboard... [siguen]
abiertos en SOL-098"* (``src/addons/sale_management/admin_views.py:9-16``).
Las clases ``TestTransicionEstadoAdmin``/``TestCancelarOrdenAdmin``/
``TestDashboardTransaccional`` de este módulo probaban ``PATCH .../status/``,
``POST .../cancellations/`` y ``GET /api/v2/admin/dashboard/`` — ninguna de
las tres rutas existe (verificado: ningún ``urls.py``/``admin_urls.py`` del
árbol las registra). Se retiran hasta que SOL-098 las resuelva; lo que sigue
vigente (seguridad + búsqueda/filtro del listado) se conserva.

**Hallazgo de código cerrado en este pase** (no de los tests): ``_admin_orders()``
(``src/addons/sale_management/admin_views.py``) hacía
``prefetch_related('order_line__product__images',
'order_line__variant__option', …)`` — ninguna de las dos rutas existe
(``product.ProductProduct`` no tiene ``images``; ``sale.SaleOrderLine`` no
tiene ``variant``, ver H-API-213). Cualquier orden con líneas hacía que el
listado/detalle admin devolviera 500. Corregido en el mismo pase (se retiran
las dos rutas rotas del prefetch). ``OrderItemSerializer.get_sku``/
``get_image_url`` y ``OrderListSerializer.get_thumbnail_url``
(``src/addons/sale/serializers.py``) tenían el mismo drift
(``product.sku``/``product.images``) — también corregido (``sku`` →
``default_code``; imagen degradada a ``None`` en vez de crashear, con la
galería real pendiente de rediseño de producto).
"""
import pytest
from decimal import Decimal

from addons.sale.models import SaleOrder, SaleOrderLine
from addons.delivery.models.sale_order import set_delivery_line
from addons.delivery.models import DeliveryAddress
from django.contrib.auth import get_user_model
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.integration

ADMIN_LIST_URL   = '/api/v2/admin/orders/'
ADMIN_DETAIL_URL = lambda o: f'/api/v2/admin/orders/{o}/'


@pytest.fixture
def prod_adm(db):
    cat = make_category(name='Cat Admin')
    return make_product(name='Elekes Admin', price=Decimal('900.00'),
                        stock=10, categ=cat, default_code='ADM-001')


def _make_order(user, prod, status='PENDING'):
    """Venta confirmada + línea de ``prod`` + envío materializado ($80,
    misma cifra histórica) + dirección de entrega.
    """
    order = make_order(user=user, status=status)
    SaleOrderLine.objects.create(
        order=order, name=prod.name,
        price_unit=prod.lst_price, product_uom_qty=1,
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
            login='oa@practicayoruba.mx', password='pass'
        )
        _make_order(user, prod_adm)
        _make_order(other, prod_adm)

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
        _make_order(user, prod_adm, 'PENDING')
        _make_order(user, prod_adm, 'SHIPPED')

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
        UI admin pueda renderizar la columna 'Comprador'."""
        _make_order(user, prod_adm, 'PENDING')
        res = admin_client.get(ADMIN_LIST_URL)
        assert res.status_code == 200
        results = res.json()['results']
        assert results, 'al menos una orden'
        first = results[0]
        assert first['user_email'] == user.email
        assert first['user_username'] == user.email

    def test_admin_detalle_de_orden(self, admin_client, user, prod_adm, db):
        order = _make_order(user, prod_adm)
        res = admin_client.get(ADMIN_DETAIL_URL(order.name))
        assert res.status_code == 200
        assert res.json()['order_number'] == order.name

    def test_admin_detalle_orden_inexistente_404(self, admin_client, db):
        res = admin_client.get(ADMIN_DETAIL_URL('S99999'))
        assert res.status_code == 404
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'
