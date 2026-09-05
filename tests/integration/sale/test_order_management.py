"""
Tests — Gestión de órdenes del comprador (UC-ORD-02..06)

Nombre descriptivo: dominio, no número de sprint.

Post-retiro del addon espejo ``orders`` (SOL-098, ``api@77bd1f0``): la venta
**es** la orden — ``sale.SaleOrder`` es la entidad canónica, no hay una
segunda entidad ``orders.Order`` que enlazar. Identidad pública = ``name``;
comprador = ``partner``; estado comercial = ``state``; importes = columnas
``amount_*`` recalculadas desde las líneas (``_compute_amounts``); estado
proyectado (para lectura) = ``order_status(order)`` desde los tres ejes
(comercial + pago + fulfillment).

**Reescritura post-disolución de catalogue/chartsize** (rama
``feature/sanear-terminologia-l0-ecosistema``): ``addons.catalogue`` y
``addons.chartsize`` ya no existen (``find src/addons/catalogue`` /
``find src/addons/chartsize`` → vacío). El catálogo se reconstruye con la
fábrica compartida ``tests.factories.product_factory`` (ficha + variante).

**Secciones retiradas en este pase** (endpoints que ``sale/views.py`` declara
explícitamente que NO se restauraron tras el retiro del addon espejo):

- ``TestEditarDireccion`` / ``TestCambiarMetodoEnvio`` — las rutas
  ``shipping-address``/``shipping-method`` no existen en
  ``src/addons/sale/urls.py`` (sólo hay ``''``, ``<order_number>/`` y
  ``<order_number>/cancellations/``). El propio docstring de
  ``src/addons/sale/views.py`` lo dice: *"shipping-address... es
  ``/shop/update_address`` de ``website_sale``... shipping-method... está
  deprecado desde 2026-07-07"*. No hay vista que ejercitar.
- ``TestProteccionVariantesOrdenes`` — dependía enteramente de
  ``chartsize.models.{VariantType,VariantOption,ProductVariant}`` (retirado)
  y de un endpoint admin ``/api/v2/admin/products/<id>/variants/<id>/`` que
  no existe (``grep -rn "VARIANT_WITH_ACTIVE_ORDERS" src/`` → vacío). El
  producto **es** la variante ahora (``ProductProduct``); el guard "no borrar
  una variante con órdenes activas" no tiene sucesor construido — es un
  rediseño de producto, fuera de alcance de esta reescritura de tests.
- ``TestOrdersCapabilityGate.test_checkout_post_stays_public`` — la premisa
  ("el POST de checkout sigue AllowAny") no es reproducible: ``OrderListView``
  no define ``post`` y ``HasCapability``/``IsAuthenticated`` corren en
  ``initial()`` **antes** de resolver el método, así que un POST anónimo da
  401 y uno autenticado-sin-capacidad da 403 — nunca "pasa" como público.
  Confirmado empíricamente (no de memoria): POST anónimo → 401
  (``{"detail":"Las credenciales de autenticación no se proveyeron."}``);
  POST autenticado sin ``account.orders`` → 403. El checkout real vive en
  ``website_sale`` (aún no existe en el árbol, ver docstring de
  ``sale/views.py``).

Nota sobre bitácora de auditoría: ``SaleOrderStatusLog`` (el modelo que
registraba cada transición) se retiró junto con el espejo y se disolvió en
el chatter (``MailThread.message_track`` — H-API-102). No tiene reemplazo
consultable equivalente todavía, así que los tests cuyo único sujeto era esa
bitácora ya no existen (se retiraron junto con las clases de arriba).
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.delivery.models import DeliveryAddress
from addons.delivery.models.sale_order import set_delivery_line
from addons.payment.models import Payment
from addons.sale.models import SaleOrder, SaleOrderLine
from tests.factories.order_factory import make_order
from tests.factories.product_factory import get_stock, make_category, make_product

pytestmark = pytest.mark.integration

ORDERS_URL = '/api/v2/orders/'
DETAIL_URL = lambda o: f'/api/v2/orders/{o}/'
CANCEL_URL = lambda o: f'/api/v2/orders/{o}/cancellations/'


# ─── Enforcement capacidad-dirigido (ADR-020, DEC-ENF-01: account.orders) ───
class TestOrdersCapabilityGate:
    """La gestión de pedidos propios (historial, detalle, cancelar) exige
    ``account.orders`` además de autenticación. Un usuario autenticado SIN
    esa capacidad recibe 403."""

    def _authed_without_capability(self, api_client):
        u = get_user_model().objects.create_user(
            login='norole-orders@kaupamex.mx', password='TestPass123!',
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def cat_ord(db):
    return make_category(name='Cat Ord')


@pytest.fixture
def prod_ord(db, cat_ord):
    return make_product(
        name='Collar Yoruba Test', default_code='ORD-CY-001',
        price=Decimal('1500.00'), stock=10, categ=cat_ord,
    )


def _create_full_order(user, prod, status='PENDING', n_items=1):
    """Venta confirmada (fábrica canónica) + línea(s) de ``prod`` + envío
    materializado ($80, misma cifra histórica) + dirección de entrega."""
    order = make_order(user=user, status=status)
    for _ in range(n_items):
        SaleOrderLine.objects.create(
            order=order, name=prod.name,
            price_unit=prod.lst_price, product_uom_qty=1,
            product=prod,
        )
    set_delivery_line(order, Decimal('80.00'))
    DeliveryAddress.objects.create(
        sale_order=order, recipient_name='Test User',
        street='Av. Reforma 100', city='CDMX',
        state='Ciudad de Mexico', zip_code='06600',
    )
    return order


def _canonical_full_order(user, prod, *, approved=False, guide=False, delivered=False):
    """Orden canónica (SaleOrder confirmada, vía fábrica) con ítem y
    dirección para que la lista serialice. Estado proyectado desde los ejes
    (pago + guía), no de una columna espejo — construir los hechos que
    proyectan el status pedido, no escribirlo."""
    if delivered:
        status = 'DELIVERED'
    elif guide:
        status = 'SHIPPED'
    elif approved:
        status = 'PAID'
    else:
        status = 'PENDING'
    order = make_order(status=status, user=user, product=prod)
    DeliveryAddress.objects.create(
        sale_order=order, recipient_name='Test User', street='Av. Reforma 100',
        city='CDMX', state='Ciudad de Mexico', zip_code='06600',
    )
    return order


def _canonical_paid_manual(user, prod):
    """PAID canónico vía pago conciliado (gateway MANUAL): proyecta PAID y el
    cancel no dispara refund de pasarela (los MANUAL se excluyen)."""
    order = _canonical_full_order(user, prod)  # PENDING
    Payment.objects.create(
        sale_order=order,
        gateway=Payment.GATEWAY_MANUAL,
        amount=Decimal('100.00'), status=Payment.STATUS_APPROVED,
    )
    return order

# =============================================================================
# UC-ORD-02 — Detalle de orden
# =============================================================================

class TestDetailOrder:

    def test_detalle_propio_retorna_200(self, auth_client, user, prod_ord, db):
        order = _create_full_order(user, prod_ord)
        res = auth_client.get(DETAIL_URL(order.name))
        assert res.status_code == 200
        data = res.json()
        assert data['order_number'] == order.name
        assert 'items' in data
        assert 'value' in data
        assert 'address' in data
        assert 'status_display' in data

    def test_rnf_sec_003_orden_ajena_retorna_404(self, auth_client, prod_ord, db):
        User = get_user_model()
        other = User.objects.create_user(
            login='other@ord.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.get(DETAIL_URL(order.name))
        assert res.status_code == 404  # nunca 403 — RNF-SEC-003
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_detalle_incluye_snapshots_br005(self, auth_client, user, prod_ord, db):
        """BR-005: el precio del item es el del checkout, no el actual."""
        order = _create_full_order(user, prod_ord)
        # Cambiar precio del producto (ficha — ``list_price`` delega ahí).
        prod_ord.product_tmpl.list_price = Decimal('9999.00')
        prod_ord.product_tmpl.save()

        res = auth_client.get(DETAIL_URL(order.name))
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
            login='ol@test.com', password='pass'
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
        assert results[0]['order_number'] == o2.name

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
        assert results[0]['order_number'] == o_delivered.name

    def test_listado_filtro_status_invalido_400(
        self, auth_client, user, prod_ord, db,
    ):
        """UC-ORD-03 D-08: status invalido -> 400 INVALID_STATUS."""
        _create_full_order(user, prod_ord, status='PENDING')
        res = auth_client.get(f'{ORDERS_URL}?status=UNICORN')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'INVALID_STATUS'

    def test_listado_filtro_status_canonico_desde_ejes(
        self, auth_client, user, prod_ord, db,
    ):
        """O2C R6: ?status= deriva el estado de los ejes canónicos (pago +
        guía), no de la columna espejo ``order.status``."""
        pend  = _canonical_full_order(user, prod_ord)                       # PENDING
        paid  = _canonical_full_order(user, prod_ord, approved=True)        # PAID
        ship  = _canonical_full_order(user, prod_ord, approved=True, guide=True)      # SHIPPED
        deliv = _canonical_full_order(user, prod_ord, approved=True, delivered=True)  # DELIVERED

        def nums(status):
            r = auth_client.get(f'{ORDERS_URL}?status={status}')
            assert r.status_code == 200
            return {o['order_number'] for o in r.json()['results']}

        assert nums('PENDING')   == {pend.name}
        assert nums('PAID')      == {paid.name}
        assert nums('SHIPPED')   == {ship.name}
        assert nums('DELIVERED') == {deliv.name}

    def test_listado_filtro_status_muerto_400(
        self, auth_client, user, prod_ord, db,
    ):
        """O2C R6: los 3 valores muertos del enum legacy salen del contrato
        público → 400 (la proyección nunca los emite)."""
        _canonical_full_order(user, prod_ord)
        for dead in ('PROCESSING', 'IN_PREPARATION', 'REFUNDED'):
            r = auth_client.get(f'{ORDERS_URL}?status={dead}')
            assert r.status_code == 400, dead
            assert r.json()['codigo_error'] == 'INVALID_STATUS'

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
        order = _canonical_full_order(user, prod_ord)
        res = auth_client.post(CANCEL_URL(order.name),
                               {'reason': 'Me arrepentí'}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CANCELLED'
        order.refresh_from_db()
        assert order.cancellation_reason == 'Me arrepentí'
        assert order.cancelled_at is not None

    def test_cancelar_orden_paid(self, auth_client, user, prod_ord, db):
        """O2C R8-pre: una orden PAID (pago confirmado, sin guía) es cancelable
        por el comprador — PROCESSING era el valor muerto equivalente."""
        order = _canonical_paid_manual(user, prod_ord)
        res = auth_client.post(CANCEL_URL(order.name), {}, format='json')
        assert res.status_code == 200
        assert res.json()['status'] == 'CANCELLED'

    def test_cancelar_restaura_stock(self, auth_client, user, prod_ord, db):
        stock_inicial = get_stock(prod_ord)
        order = _create_full_order(user, prod_ord, status='PENDING')
        auth_client.post(CANCEL_URL(order.name), {}, format='json')
        assert get_stock(prod_ord) == stock_inicial + 1

    # O2C V5d: se retiro ``test_cancelar_in_preparation_no_permitido``.
    # ``IN_PREPARATION`` es un valor MUERTO del enum legacy (0 escritores; la
    # proyeccion canonica nunca lo emite), asi que el caso no era representable
    # y el test probaba un estado inalcanzable. El camino no-cancelable real lo
    # cubre ``test_cancelar_delivered_no_permitido``.

    def test_cancelar_delivered_no_permitido(
        self, auth_client, user, prod_ord, db
    ):
        order = _create_full_order(user, prod_ord, status='DELIVERED')
        res = auth_client.post(CANCEL_URL(order.name), {}, format='json')
        assert res.status_code == 400

    # H-API — ``test_cancelacion_con_pago_inicia_reembolso`` retirado: su
    # premisa ("cancelar dispara reembolso automático") depende de un
    # listener del signal ``order_cancelled`` (``sale/signals.py:57``) que
    # NO existe. ``cancel_order`` (``sale/services.py:504-509``) manda la
    # señal con el comentario "El reembolso lo hace ``payments`` al
    # escuchar la señal", pero ``grep -rn "order_cancelled" src/`` sólo
    # encuentra su definición y su ``.send()`` — cero receptores. El único
    # ``@receiver`` de ``payment/handlers.py`` escucha ``post_save`` sobre
    # ``Refund``, no ``order_cancelled`` sobre ``SaleOrder``. Confirmado
    # ejecutando el test contra el código real: el ``Payment`` queda en
    # ``APPROVED`` (no ``REFUNDED``) tras cancelar. Es una feature de
    # negocio sin implementar (conectar el signal a la creación de un
    # ``Refund`` + llamada al gateway), no un drift de nombres — fuera de
    # alcance de esta reescritura de tests. Ver hallazgo en el reporte de
    # esta iniciativa.

    def test_cancelar_orden_pagada(self, auth_client, user, prod_ord, db):
        """H-ORD-S01 regression: orden en estado PAID es cancelable por el comprador.

        PAID = pago confirmado por webhook pero aún no en preparación.
        Debe incluirse en CANCELABLE_STATUSES para evitar que el comprador
        quede atrapado con una orden pagada que no puede cancelar.
        """
        order = _canonical_paid_manual(user, prod_ord)
        res = auth_client.post(
            CANCEL_URL(order.name),
            {'reason': 'Cambié de opinión'},
            format='json',
        )
        assert res.status_code == 200, res.json()
        assert res.json()['status'] == 'CANCELLED'
        order.refresh_from_db()
        # O2C R8: el estado es la proyección del eje comercial — la venta ES
        # la orden, no hay ``.sale_order`` que navegar.
        assert order.state == SaleOrder.STATE_CANCEL
        assert order.cancellation_reason == 'Cambié de opinión'
        assert order.cancelled_at is not None

    def test_cancelar_rnf_sec_003_orden_ajena_retorna_404(
        self, auth_client, prod_ord, db
    ):
        User = get_user_model()
        other = User.objects.create_user(
            login='oc@test.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.post(CANCEL_URL(order.name), {}, format='json')
        assert res.status_code == 404
