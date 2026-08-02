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

Nota sobre bitácora de auditoría: ``SaleOrderStatusLog`` (el modelo que
registraba cada transición) se retiró junto con el espejo y se disolvió en
el chatter (``MailThread.message_track`` — H-API-102). No tiene reemplazo
consultable equivalente todavía, así que los tests cuyo único sujeto era esa
bitácora (``test_editar_direccion_registra_auditoria``,
``test_cambiar_envio_registra_auditoria``) se retiraron en este pase; no se
reencuadran porque no hay eje canónico de reemplazo que probar.
"""
import pytest
from decimal import Decimal
from addons.catalogue.models import Category, Product
from django.contrib.auth import get_user_model
from tests.factories.user_factory import make_buyer
from addons.payment.models import Payment, Refund
from addons.delivery.models import ShippingMethod, Courier, ShipmentGuide, DeliveryAddress
from addons.delivery.models.sale_order import set_delivery_line
from addons.payment.models import PaymentGateway
from django.utils import timezone

from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.amounts import order_amounts
from unittest.mock import patch, MagicMock
from addons.chartsize.models import VariantType, VariantOption, ProductVariant
from tests.factories.order_factory import make_order

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
    """Venta confirmada (fábrica canónica) + línea(s) de ``prod`` + envío
    materializado ($80, misma cifra histórica) + dirección de entrega."""
    order = make_order(user=user, status=status)
    for _ in range(n_items):
        SaleOrderLine.objects.create(
            order=order, name=prod.name,
            price_unit=prod.price, product_uom_qty=1,
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

class TestDetalleOrden:

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
            email='other@ord.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.get(DETAIL_URL(order.name))
        assert res.status_code == 404  # nunca 403 — RNF-SEC-003
        assert res.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    def test_detalle_incluye_snapshots_br005(self, auth_client, user, prod_ord, db):
        """BR-005: el precio del item es el del checkout, no el actual."""
        order = _create_full_order(user, prod_ord)
        # Cambiar precio del producto
        prod_ord.price = Decimal('9999.00')
        prod_ord.save()

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
        stock_inicial = prod_ord.stock
        order = _create_full_order(user, prod_ord, status='PENDING')
        auth_client.post(CANCEL_URL(order.name), {}, format='json')
        prod_ord.refresh_from_db()
        assert prod_ord.stock == stock_inicial + 1

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

    def test_cancelacion_con_pago_inicia_reembolso(
        self, auth_client, user, prod_ord, db
    ):
        """H-ORD-004: cancelar orden PAID con Payment → reembolso automático.

        La orden se construye PENDING y el ``Payment`` MERCADOPAGO se agrega
        a mano (no vía ``status='PAID'`` de la fábrica) para no confundir el
        flujo con el ``Payment`` MANUAL que la fábrica agregaría — este caso
        exige exactamente un pago de pasarela real, elegible a reembolso.
        """

        gw = PaymentGateway(name='MP', gateway='MERCADOPAGO', is_active=True)
        gw.set_credentials({'access_token': 'T', 'client_secret': 'S'})
        gw.save()

        order = _create_full_order(user, prod_ord, status='PENDING')
        payment = Payment.objects.create(
            sale_order=order, gateway='MERCADOPAGO',
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
                CANCEL_URL(order.name),
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
            email='oc@test.com', password='pass'
        )
        order = _create_full_order(other, prod_ord)
        res = auth_client.post(CANCEL_URL(order.name), {}, format='json')
        assert res.status_code == 404


# =============================================================================
# UC-ORD-05 — Editar dirección
# =============================================================================

class TestEditarDireccion:

    def test_editar_direccion_orden_pending(self, auth_client, user, prod_ord, db):
        order = _create_full_order(user, prod_ord, status='PENDING')
        res = auth_client.patch(ADDRESS_URL(order.name), {
            'recipient_name': 'Nuevo Destinatario',
            'street':         'Calle Nueva 999',
            'city':           'Guadalajara',
            'state':          'Jalisco',
            'zip_code':       '44100',
        }, format='json')
        assert res.status_code == 200
        order.refresh_from_db()
        assert order.delivery_address.city == 'Guadalajara'

    def test_editar_direccion_paid_permitido(
        self, auth_client, user, prod_ord, db
    ):
        """O2C R8-pre: PAID y aún sin guía — edición de dirección permitida
        (IN_PREPARATION era el valor muerto equivalente)."""
        order = _create_full_order(user, prod_ord, status='PAID')
        res = auth_client.patch(ADDRESS_URL(order.name), {
            'recipient_name': 'Prueba', 'street': 'St 1',
            'city': 'MTY', 'state': 'NL', 'zip_code': '64000',
        }, format='json')
        assert res.status_code == 200

    def test_editar_direccion_shipped_no_permitido(
        self, auth_client, user, prod_ord, db
    ):
        order = _create_full_order(user, prod_ord, status='SHIPPED')
        res = auth_client.patch(ADDRESS_URL(order.name), {
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
        res = auth_client.patch(ADDRESS_URL(order.name), {
            'recipient_name': 'X', 'street': 'Y',
            'city': 'Z', 'state': 'W', 'zip_code': '00000',
        }, format='json')
        assert res.status_code == 404

    # H-API-05 (T-005/ORD-05) — ``test_editar_direccion_registra_auditoria``
    # se retiró en el cut-over orders→sale (SOL-098). Su único sujeto era
    # ``SaleOrderStatusLog`` (bitácora de cambios), modelo disuelto en el
    # chatter (``MailThread.message_track``, H-API-102) sin API de lectura
    # equivalente todavía. No se reencuadra: no hay eje canónico consultable
    # que sustituya la aserción original (conteo de logs + campos del log).


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
        order.carrier = shipping_methods['express']
        order.save(update_fields=['carrier', 'updated_at'])
        set_delivery_line(order, Decimal('150.00'))

        res = auth_client.patch(SHIPPING_URL(order.name), {
            'shipping_method_id': shipping_methods['standard'].pk,
        }, format='json')

        assert res.status_code == 200
        order.refresh_from_db()
        # H-ORD-007: el envío materializa como línea marcada (is_delivery);
        # amount_total recalcula automáticamente vía _compute_amounts al
        # cambiar la línea. El desglose de comprador se lee de order_amounts
        # (mismo contrato de 5 claves que el OrderValue retirado, E4).
        value = order_amounts(order)
        assert Decimal(value['shipping_cost']) == Decimal('50.00')

    def test_cambiar_envio_shipped_no_permitido(
        self, auth_client, user, prod_ord, shipping_methods, db
    ):
        """UC-ORD-06 PARTE 7.3 (DEC-ORD-04): orden en estado no-editable
        -> 409 ORDER_NOT_EDITABLE (antes 400 METHOD_NOT_EDITABLE)."""
        order = _create_full_order(user, prod_ord, status='SHIPPED')
        res = auth_client.patch(SHIPPING_URL(order.name), {
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
        # V5d: ``IN_PREPARATION`` es valor muerto (inalcanzable) — solo PAID.
        for paid_status in ('PAID',):
            order = _create_full_order(user, prod_ord, status=paid_status)
            res = auth_client.patch(SHIPPING_URL(order.name), {
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
        res = auth_client.patch(SHIPPING_URL(order.name), {
            'shipping_method_id': 99999,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'SHIPPING_METHOD_NOT_AVAILABLE'

    # H-API-06 (T-007-audit/ORD-06) — ``test_cambiar_envio_registra_auditoria``
    # se retiró por la misma razón que su hermana de UC-ORD-05: su único
    # sujeto era ``SaleOrderStatusLog``, sin reemplazo consultable (ver nota
    # en ``TestEditarDireccion``).


# =============================================================================
# VARIANTE_CON_ORDENES — H-ORD-005
# =============================================================================

class TestProteccionVariantesOrdenes:
    """H-ORD-005 tras cut-over orders→sale (ADR-024): "orden activa" =
    confirmada (``sale.state='sale'``) y NO entregada. Los fixtures
    construyen los ejes canónicos (SaleOrder confirmada + guía) — la venta
    ES la orden, no hay una segunda entidad que enlazar."""

    def _make_variant(self, prod_ord):
        vtype = VariantType.objects.create(name='Talla', product=prod_ord)
        vopt  = VariantOption.objects.create(
            variant_type=vtype, label='M', slug='m'
        )
        return ProductVariant.objects.create(
            product=prod_ord, option=vopt, sku_suffix='M',
            price_override=Decimal('1500'), stock=5, is_active=True,
        )

    def _make_order_with_variant(self, prod_ord, variant):
        """Venta confirmada con una línea de la variante (E2c: el guard de
        la vista lee ``SaleOrderLine`` — el fixture construye la línea
        canónica directo, sin segunda entidad que enlazar)."""
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_SALE, date_order=timezone.now())
        SaleOrderLine.objects.create(
            order=order, product=prod_ord, variant=variant,
            name=prod_ord.name, product_uom_qty=1,
            price_unit=variant.price_override,
        )
        return order

    def test_no_eliminar_variante_con_orden_activa(self, admin_client, prod_ord, db):
        """Variante en orden confirmada sin guía entregada → 400."""
        variant = self._make_variant(prod_ord)
        self._make_order_with_variant(prod_ord, variant)

        res = admin_client.delete(
            f'/api/v2/admin/products/{prod_ord.pk}/variants/{variant.pk}/')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VARIANT_WITH_ACTIVE_ORDERS'

    def test_eliminar_variante_con_orden_entregada_permitido(
        self, admin_client, prod_ord, db
    ):
        """Orden entregada (guía DELIVERED viva) NO bloquea → 204."""
        variant = self._make_variant(prod_ord)
        order = self._make_order_with_variant(prod_ord, variant)
        courier = Courier.objects.create(name='Estafeta', code='EST')
        ShipmentGuide.objects.create(
            sale_order=order, courier=courier,
            tracking_number='TRK-DELIVERED-1',
            status=ShipmentGuide.STATUS_DELIVERED,
        )

        res = admin_client.delete(
            f'/api/v2/admin/products/{prod_ord.pk}/variants/{variant.pk}/')
        assert res.status_code == 204
        variant.refresh_from_db()
        assert variant.is_active is False
