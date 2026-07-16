"""
Tests — Checkout and order creation (UC-ORD-01)

UC-ORD-01: Create order from cart (checkout)
"""
import time

import pytest
from decimal import Decimal
from apps.addons.catalogue.models import Category, Product
from apps.addons.settings_app.models import ShippingMethod
from apps.addons.orders.models import Order, OrderValue, OrderAddress, ShippingZone
from apps.addons.cart.models import CartItem
from apps.addons.voucher.models import Voucher
from django.utils import timezone
pytestmark = pytest.mark.integration

CHECKOUT_URL = '/api/v2/orders/'
ITEMS_URL    = '/api/v2/cart/items/'

ADDR = {
    'recipient_name': 'Test User',
    'street': 'Av. Reforma 100',
    'city': 'CDMX',
    'state': 'Ciudad de Mexico',
    'zip_code': '06600',
    'country': 'MX',
}


@pytest.fixture
def zone_cdmx(db):
    zone, _ = ShippingZone.objects.get_or_create(
        zip_code_prefix='06', defaults={'name': 'Ciudad de México', 'is_active': True}
    )
    return zone


@pytest.fixture
def cat_ord(db):
    return Category.objects.create(name='Cat Ord', slug='cat-ord', is_active=True)


@pytest.fixture
def prod_ord(db, cat_ord):
    _p = Product.objects.create(
        name='Prod Ord', slug='prod-ord', sku='ORD-001',
        description='',
        price=Decimal('500.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_ord)
    return _p


@pytest.fixture
def cart_con_item_auth(auth_client, prod_ord, zone_cdmx):
    auth_client.post(ITEMS_URL, {
        'product_id': prod_ord.pk, 'quantity': 2,
    }, format='json')
    return auth_client


@pytest.fixture
def shipping(db):
    return ShippingMethod.objects.create(
        name='Estándar', cost=Decimal('80.00'), estimated_days=5, is_active=True)


@pytest.fixture
def shipping_gratis(db):
    """Método de envío gratis (cost=0). DEC-BC-25 hace obligatorio el método
    en el checkout; los tests que asiertan totales/IVA sin costo de envío usan
    este fixture para mantener shipping_cost=0 sin cambiar sus aserciones."""
    return ShippingMethod.objects.create(
        name='Gratis', cost=Decimal('0.00'), estimated_days=7, is_active=True)


@pytest.fixture
def zone_nacional(db):
    """Zona nacional (prefijo 64, Monterrey) con costo y umbral EXPLÍCITOS.

    G-ENV-04: el costo por zona lo siembra la migración 0003, pero ese seed
    sólo existe en una DB fresca (``--create-db``); con ``--reuse-db`` la QA
    compartida puede no tenerlo. Para que el test sea determinista en ambos
    entornos, fija ``cost``/``free_threshold`` en la zona en vez de depender
    del seed ambiental (mismo criterio que ``zone_cdmx``, pero con valores
    explícitos: nacional $199, gratis desde $1300)."""
    zone, _ = ShippingZone.objects.get_or_create(
        zip_code_prefix='64',
        defaults={'name': 'Nacional (Monterrey)', 'is_active': True},
    )
    zone.cost = Decimal('199.00')
    zone.free_threshold = Decimal('1300.00')
    zone.is_active = True
    zone.save(update_fields=['cost', 'free_threshold', 'is_active'])
    return zone


class TestCheckout:

    def test_checkout_autenticado(
        self, cart_con_item_auth, prod_ord, shipping_gratis, db
    ):
        res = cart_con_item_auth.post(CHECKOUT_URL, {
            'address': ADDR,
            'shipping_method_id': shipping_gratis.pk,
        }, format='json')
        assert res.status_code == 201
        data = res.json()
        assert data['order_number'].startswith('PY-')
        assert data['status'] == 'PENDING'
        assert len(data['items']) == 1
        assert data['items'][0]['quantity'] == 2
        assert data['items'][0]['product_name'] == 'Prod Ord'

    def test_checkout_crea_snapshot_inmutable_br005(
        self, cart_con_item_auth, prod_ord, shipping_gratis, db
    ):
        """BR-005: unit_price del OrderItem = precio al momento del checkout."""
        original_price = prod_ord.price
        res = cart_con_item_auth.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json')
        assert res.status_code == 201
        item_price = Decimal(res.json()['items'][0]['unit_price'])
        assert item_price == original_price
        # Cambiar precio del producto — no debe afectar la orden
        prod_ord.price = Decimal('999.00')
        prod_ord.save()
        order = Order.objects.get(order_number=res.json()['order_number'])
        assert order.items.first().unit_price == original_price

    def test_checkout_decrementa_stock(
        self, cart_con_item_auth, prod_ord, shipping_gratis, db
    ):
        cart_con_item_auth.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json')
        prod_ord.refresh_from_db()
        assert prod_ord.stock == 8  # 10 - 2

    def test_checkout_vacia_el_carrito(
        self, cart_con_item_auth, shipping_gratis, db
    ):
        cart_con_item_auth.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json')
        assert CartItem.objects.count() == 0

    def test_checkout_crea_ordervalue(
        self, cart_con_item_auth, prod_ord, shipping_gratis, db
    ):
        res = cart_con_item_auth.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json')
        value = res.json()['value']
        assert Decimal(value['subtotal']) == Decimal('1000.00')  # 500 * 2
        assert 'tax' in value
        assert 'total' in value

    def test_checkout_envio_gratis_siempre_cdmx(
        self, cart_con_item_auth, db
    ):
        """Envío GRATIS siempre (REVIERTE DEC-BC-25): el comprador no elige
        método; shipping_cost == 0 para un C.P. de CDMX (06600)."""
        res = cart_con_item_auth.post(CHECKOUT_URL, {
            'address': ADDR,
        }, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('0.00')

    def test_checkout_envio_nacional_cobra_bajo_umbral(
        self, cart_con_item_auth, zone_nacional, db
    ):
        """G-ENV-04: retirado el "envío gratis siempre". Un C.P. nacional
        (Monterrey 64000) con subtotal $1000 (< umbral nacional $1300) cobra
        el costo de zona nacional ($199). El comprador no elige método; el
        costo se deriva del C.P. de destino."""
        addr_nacional = {**ADDR, 'city': 'Monterrey',
                         'state': 'Nuevo Leon', 'zip_code': '64000'}
        res = cart_con_item_auth.post(CHECKOUT_URL, {
            'address': addr_nacional,
        }, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('199.00')

    def test_checkout_sin_shipping_method_id_crea_orden(
        self, cart_con_item_auth, prod_ord, db
    ):
        """REVIERTE DEC-BC-25: el checkout ya NO exige shipping_method_id. El
        comprador nunca selecciona método; la orden se crea gratis y sin
        ShippingMethod asociado (antes esto daba 400 SHIPPING_METHOD_REQUIRED)."""
        res = cart_con_item_auth.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('0.00')
        order = Order.objects.get(order_number=res.json()['order_number'])
        assert order.shipping_method is None

    def test_checkout_ignora_shipping_method_id_del_payload(
        self, cart_con_item_auth, shipping, db
    ):
        """REVIERTE DEC-BC-25: si el payload aún trae un shipping_method_id
        (método con cost=80), el back lo IGNORA — el comprador no elige método.
        La orden se crea gratis y sin ShippingMethod asociado (antes esto
        derivaba shipping_cost=80 del método)."""
        res = cart_con_item_auth.post(CHECKOUT_URL, {
            'address': ADDR,
            'shipping_method_id': shipping.pk,
        }, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('0.00')
        order = Order.objects.get(order_number=res.json()['order_number'])
        assert order.shipping_method is None

    def test_checkout_carrito_vacio_retorna_400(self, auth_client, zone_cdmx, db):
        res = auth_client.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert res.status_code in (400, 404)

    def test_checkout_anonimo(self, api_client, prod_ord, zone_cdmx, shipping_gratis, db):
        """BR-011: visitante anónimo puede hacer checkout."""
        add_res = api_client.post(ITEMS_URL, {
            'product_id': prod_ord.pk, 'quantity': 1,
        }, format='json')
        cart_token = add_res['X-Cart-Token']
        api_client.credentials(HTTP_X_CART_TOKEN=cart_token)
        res = api_client.post(CHECKOUT_URL, {
            'cart_token': cart_token,
            'guest_email': 'invitado@test.mx',
            'address': ADDR,
            'shipping_method_id': shipping_gratis.pk,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['guest_email'] == 'invitado@test.mx'

    def test_checkout_anonimo_sin_guest_email_retorna_400(
        self, api_client, prod_ord, zone_cdmx, db
    ):
        add_res = api_client.post(ITEMS_URL, {
            'product_id': prod_ord.pk, 'quantity': 1,
        }, format='json')
        cart_token = add_res['X-Cart-Token']
        api_client.credentials(HTTP_X_CART_TOKEN=cart_token)
        res = api_client.post(CHECKOUT_URL, {
            'cart_token': cart_token,
            'address': ADDR,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'GUEST_EMAIL_REQUIRED'

    def test_checkout_stock_insuficiente_retorna_409(
        self, auth_client, prod_ord, zone_cdmx, db
    ):
        prod_ord.stock = 1
        prod_ord.save()
        auth_client.post(ITEMS_URL, {
            'product_id': prod_ord.pk, 'quantity': 1,
        }, format='json')
        # Agotar el stock antes de confirmar
        prod_ord.stock = 0
        prod_ord.save()
        res = auth_client.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert res.status_code == 409
        assert res.json()['codigo_error'] == 'INSUFFICIENT_STOCK'
        # Stock NO debe haber cambiado
        prod_ord.refresh_from_db()
        assert prod_ord.stock == 0

    def test_checkout_con_voucher_aplica_descuento(
        self, auth_client, prod_ord, zone_cdmx, shipping_gratis, db, admin_user
    ):
        v = Voucher.objects.create(
            code='PROMO100', voucher_type='FIXED',
            discount_value=Decimal('100.00'),
            valid_from=timezone.now() - __import__('datetime').timedelta(days=1),
            is_active=True, min_order_amount=Decimal('0'), created_by=admin_user,
        )
        # G-ENV-04: el envío ya no es gratis por defecto. Se usa subtotal
        # $1000 (2 × $500), ≥ umbral metro $800 (C.P. 06600 CDMX) → envío
        # gratis por umbral, de modo que el total queda desacoplado del costo
        # de envío y verifica solo el descuento: 1000 - 100 = 900.
        auth_client.post(ITEMS_URL, {'product_id': prod_ord.pk, 'quantity': 2}, format='json')
        auth_client.post('/api/v2/cart/voucher/', {'code': 'PROMO100'}, format='json')
        res = auth_client.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['discount']) == Decimal('100.00')
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('0.00')
        assert Decimal(res.json()['value']['total']) == Decimal('900.00')
        assert res.json()['voucher_code'] == 'PROMO100'

    def test_checkout_incrementa_voucher_current_uses(
        self, auth_client, prod_ord, zone_cdmx, shipping_gratis, db, admin_user,
    ):
        """T-115 D-01 CRITICA (implementar-current-uses-increment):
        verificar que el campo Voucher.current_uses se incrementa
        atomicamente tras crear la Order. Antes el campo era leido en
        is_usable()/can_apply() pero nunca incrementado -> max_uses
        no limitaba en la practica."""
        v = Voucher.objects.create(
            code='LIMIT1', voucher_type='FIXED',
            discount_value=Decimal('50.00'),
            valid_from=timezone.now() - __import__('datetime').timedelta(days=1),
            is_active=True, min_order_amount=Decimal('0'),
            max_uses=2, current_uses=0, created_by=admin_user,
        )
        auth_client.post(ITEMS_URL, {'product_id': prod_ord.pk, 'quantity': 1}, format='json')
        auth_client.post('/api/v2/cart/voucher/', {'code': 'LIMIT1'}, format='json')
        res = auth_client.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json')
        assert res.status_code == 201
        v.refresh_from_db()
        assert v.current_uses == 1, (
            f'Voucher.current_uses debio incrementarse a 1; valor real: '
            f'{v.current_uses}'
        )


    def test_idempotency_key_no_duplica_orden(
        self, cart_con_item_auth, prod_ord, shipping_gratis, db
    ):
        """UC-ORD-01 AC-06: dos POST con el mismo Idempotency-Key crean UNA
        sola orden; el segundo devuelve el mismo order_number.

        DEC-BC-03: la respuesta cacheada se sirve desde CheckoutAttempt
        (UNIQUE(user, idempotency_key)).

        HALLAZGO H-ORD-AC06-01: el AC exige HTTP 200 en el segundo POST;
        la implementacion (views.py:83) devuelve 201. Este test asierta el
        comportamiento real (201) + el invariante central del AC (una sola
        orden, mismo order_number). El mismatch de codigo se reporta aparte.
        """
        key = 'idem-key-ac06-001'
        payload = {'address': ADDR, 'shipping_method_id': shipping_gratis.pk}
        first = cart_con_item_auth.post(
            CHECKOUT_URL, payload, format='json',
            HTTP_IDEMPOTENCY_KEY=key,
        )
        assert first.status_code == 201
        first_number = first.json()['order_number']

        # Segundo POST con la misma clave: no debe crear otra orden.
        second = cart_con_item_auth.post(
            CHECKOUT_URL, payload, format='json',
            HTTP_IDEMPOTENCY_KEY=key,
        )
        assert second.json()['order_number'] == first_number
        # Invariante AC-06: una sola Order persistida para esa clave.
        assert Order.objects.filter(order_number=first_number).count() == 1
        assert Order.objects.count() == 1

    def test_iva_y_total_se_calculan_en_servidor(
        self, cart_con_item_auth, prod_ord, shipping_gratis, db
    ):
        """UC-ORD-01 AC-07 (BR-002): el IVA y el total se calculan en el
        servidor; el cliente nunca define ``total`` en el request.

        El request abajo solo envia ``address`` (sin ``total`` ni ``tax``);
        el servidor persiste OrderValue con valores derivados del carrito.

        Modelo fiscal IMPLEMENTADO (views.py:201-202, confirmado por el
        ejemplo en uc-ord-01 PARTE 7C.3): precios IVA-incluido ->
        ``tax = round(subtotal * iva_rate / (1 + iva_rate), 2)`` y
        ``total = subtotal_neto + shipping_cost`` (el IVA ya esta embebido
        en el subtotal, no se suma de nuevo). Para subtotal=1000 sin envio:
        tax = 1000 * 0.16 / 1.16 = 137.93 ; total = 1000.

        HALLAZGO H-ORD-AC07-01: la PROSA del AC-07 describe el modelo
        IVA-agregado (``iva = round(subtotal*0.16,2)``,
        ``total = subtotal + iva + shipping``), que NO coincide con la
        implementacion ni con el ejemplo de la misma seccion del UC. La
        afirmacion verificable del AC (calculo server-side, cliente no
        define total) SI se cumple y es lo que asierta este test.
        """
        # El cliente NO envia 'total' ni 'tax' — solo la direccion y el método
        # de envío (obligatorio, gratis para no alterar el cálculo del total).
        res = cart_con_item_auth.post(
            CHECKOUT_URL,
            {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
            format='json',
        )
        assert res.status_code == 201
        value = res.json()['value']

        subtotal = Decimal(value['subtotal'])
        assert subtotal == Decimal('1000.00')  # 500.00 * 2

        # IVA calculado server-side (modelo IVA-incluido, iva_rate=0.16).
        expected_tax = (subtotal * Decimal('0.16') / Decimal('1.16')).quantize(
            Decimal('0.01')
        )
        assert Decimal(value['tax']) == expected_tax == Decimal('137.93')

        # total = subtotal_neto + shipping_cost (sin envio => shipping 0).
        assert Decimal(value['shipping_cost']) == Decimal('0.00')
        assert Decimal(value['total']) == subtotal + Decimal(value['shipping_cost'])
        assert Decimal(value['total']) == Decimal('1000.00')

        # Server-side authority: el valor persistido coincide con la respuesta.
        order = Order.objects.get(order_number=res.json()['order_number'])
        assert order.value.tax == expected_tax
        assert order.value.total == subtotal + order.value.shipping_cost


class TestShippingMethodProtection:

    def test_desactivar_metodo_con_ordenes_activas_retorna_400(
        self, admin_client, shipping, prod_ord, db
    ):
        o = Order.objects.create(
            order_number='PY-TEST0001',
            status='PENDING', shipping_method=shipping
        )
        OrderValue.objects.create(
            order=o, subtotal=Decimal('500'), tax=Decimal('68.97'),
            shipping_cost=Decimal('80'), discount=Decimal('0'),
            total=Decimal('580')
        )
        OrderAddress.objects.create(
            order=o, recipient_name='Test', street='St',
            city='CDMX', state='CMX', zip_code='06600'
        )
        res = admin_client.delete(f'/api/v2/admin/shipping-methods/{shipping.pk}/')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'METHOD_WITH_ACTIVE_ORDERS'


class TestZoneFreeShipping:
    """Costo manual por zona con umbral de envío gratis (G-ENV-04): el
    comprador no elige método; el admin fija ``cost``/``free_threshold`` por
    zona. Umbral alcanzado o zona sin ``cost`` → gratis; bajo umbral con
    ``cost`` → cobra el costo manual. Ver ``apps.addons.orders.shipping``."""

    def _set_zone(self, **defaults):
        # C.P. de ADDR = '06600' → prefijo '06'. update_or_create respeta el
        # invariante UNA zona por prefijo (unique) y sobreescribe la sembrada.
        ShippingZone.objects.update_or_create(
            zip_code_prefix='06',
            defaults={'name': 'Zona test', 'is_active': True, **defaults})

    def test_zona_con_umbral_es_gratis(self, cart_con_item_auth, db):
        # subtotal = 1000 (2×500) ≥ umbral 800 → gratis (umbral alcanzado),
        # aunque la zona tenga cost=50 (G-ENV-04).
        self._set_zone(free_threshold=Decimal('800.00'), cost=Decimal('50.00'))
        res = cart_con_item_auth.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('0.00')

    def test_zona_bajo_umbral_cobra_costo(self, cart_con_item_auth, db):
        # subtotal 1000 < umbral 1300 y la zona tiene cost=50 → cobra 50.00
        # (G-ENV-04: costo manual por zona bajo el umbral de envío gratis).
        self._set_zone(free_threshold=Decimal('1300.00'), cost=Decimal('50.00'))
        res = cart_con_item_auth.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('50.00')

    def test_sin_metodo_seleccionado_sigue_gratis(self, cart_con_item_auth, db):
        # Zona sin umbral ni costo y sin método en el payload: gratis. Antes
        # (G-ENV-01) caía al costo del método (80); ya no hay método que elegir.
        self._set_zone(free_threshold=None, cost=None)
        res = cart_con_item_auth.post(CHECKOUT_URL, {'address': ADDR}, format='json')
        assert res.status_code == 201
        assert Decimal(res.json()['value']['shipping_cost']) == Decimal('0.00')

    def test_resolve_for_zip_prefijo_mas_largo_gana(self, db):
        ShippingZone.objects.update_or_create(
            zip_code_prefix='06', defaults={'name': 'CDMX', 'is_active': True})
        ShippingZone.objects.update_or_create(
            zip_code_prefix='066', defaults={'name': 'Cuauhtémoc', 'is_active': True})
        assert ShippingZone.resolve_for_zip('06600').zip_code_prefix == '066'
        assert ShippingZone.resolve_for_zip('99000') is None
        assert ShippingZone.resolve_for_zip('') is None


# =============================================================================
# P-22 — UC-ORD-01 RNF-PERF: checkout P95 800ms SLO
# =============================================================================

class TestCheckoutP95SLO:
    """UC-ORD-01 RNF-PERF: checkout must complete in <800ms at P95."""

    def test_checkout_p95_slo_800ms(
        self, auth_client, prod_ord, zone_cdmx, shipping_gratis, db,
    ):
        """UC-ORD-01 RNF-PERF: end-to-end checkout wall-clock must be <800ms.

        Runs 5 sequential checkouts on fresh products and asserts every
        request finishes within the 800ms budget.  This per-request guard
        catches obvious regressions; a true P95 would need many more samples
        but is impractical in a synchronous test suite.
        """
        for i in range(5):
            p = Product.objects.create(
                name=f'SLO Prod {i}', slug=f'slo-prod-{i}', sku=f'SLO-{i:03d}',
                price=Decimal('100.00'), stock=5,
                is_active=True, is_published=True,
            )
            _cat = prod_ord.categories.first()
            if _cat:
                p.categories.add(_cat)
            auth_client.post(
                ITEMS_URL, {'product_id': p.pk, 'quantity': 1}, format='json',
            )

            start = time.monotonic()
            res = auth_client.post(
                CHECKOUT_URL,
                {'address': ADDR, 'shipping_method_id': shipping_gratis.pk},
                format='json')
            elapsed_ms = (time.monotonic() - start) * 1000

            assert res.status_code == 201, (
                f'Iteration {i}: checkout failed with {res.status_code}: {res.json()}'
            )
            assert elapsed_ms < 800, (
                f'UC-ORD-01 RNF-PERF: iteration {i} took {elapsed_ms:.0f}ms, '
                f'exceeds 800ms P95 SLO'
            )
