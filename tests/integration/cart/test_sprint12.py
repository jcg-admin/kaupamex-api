"""
Tests de integracion — Sprint 12
UC-CART-01: Agregar Producto al Carrito
UC-CART-02: Ver y Editar Carrito
UC-CART-03: Eliminar Item del Carrito
UC-CART-05: Guardar Carrito para Despues
UC-CART-06: Sincronizar Carrito Anonimo al Autenticar
"""
import uuid, pytest
from decimal import Decimal

pytestmark = pytest.mark.integration

CART_URL  = '/api/v1/cart/'
ITEMS_URL = '/api/v1/cart/items/'
SAVE_URL  = '/api/v1/cart/save/'
MERGE_URL = '/api/v1/cart/merge/'


@pytest.fixture
def cat_s12(db):
    from apps.catalogue.models import Category
    return Category.objects.create(name='Cat S12', slug='cat-s12', is_active=True)


@pytest.fixture
def product_sin_variante(db, cat_s12):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Prod Sin Variante', slug='prod-sin-var-s12', sku='S12-SV-001',
        description='', category=cat_s12,
        price=Decimal('800.00'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def product_con_variante(db, cat_s12):
    from apps.catalogue.models import Product
    return Product.objects.create(
        name='Prod Con Variante', slug='prod-con-var-s12', sku='S12-CV-001',
        description='', category=cat_s12,
        price=Decimal('1200.00'), stock=0,
        is_active=True, is_published=True,
    )


@pytest.fixture
def variant_s12(db, product_con_variante):
    from apps.chartsize.models import VariantType, VariantOption, ProductVariant
    vt = VariantType.objects.create(
        product=product_con_variante, name='Tamaño', order=0
    )
    opt = VariantOption.objects.create(
        variant_type=vt, label='Mediana', slug='med-s12', order=0
    )
    return ProductVariant.objects.create(
        product=product_con_variante, option=opt,
        sku_suffix='MED', stock=5, is_active=True,
    )


@pytest.fixture
def cart_token():
    return str(uuid.uuid4())


@pytest.fixture
def anon_client_with_cart(api_client, product_sin_variante):
    """Cliente anonimo con un item ya en el carrito. Retorna (client, cart_token)."""
    res = api_client.post(ITEMS_URL, {
        'product_id': product_sin_variante.pk,
        'quantity': 1,
    }, format='json')
    token = res['X-Cart-Token']
    api_client.credentials(HTTP_X_CART_TOKEN=token)
    return api_client, token


# =============================================================================
# UC-CART-01 — Agregar producto al carrito
# =============================================================================

class TestAgregarProducto:

    def test_agregar_producto_sin_variante_retorna_201(
        self, api_client, product_sin_variante, db
    ):
        res = api_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk,
            'quantity': 2,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['quantity'] == 2
        assert 'X-Cart-Token' in res  # se genera token para anonimo

    def test_agregar_producto_con_variante(
        self, api_client, product_con_variante, variant_s12, db
    ):
        res = api_client.post(ITEMS_URL, {
            'product_id': product_con_variante.pk,
            'variant_id': variant_s12.pk,
            'quantity': 1,
        }, format='json')
        assert res.status_code == 201
        assert res.json()['variant_label'] == 'Mediana'

    def test_agregar_sin_variante_cuando_producto_la_requiere_retorna_400(
        self, api_client, product_con_variante, variant_s12, db
    ):
        """FR-CHT-01.02: variante requerida si el producto tiene variantes."""
        res = api_client.post(ITEMS_URL, {
            'product_id': product_con_variante.pk,
            'quantity': 1,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VARIANTE_REQUERIDA'

    def test_upsert_incrementa_cantidad_existente(
        self, api_client, product_sin_variante, db
    ):
        """FR-CART-01.02 Escenario 2: item ya existente suma cantidad."""
        res1 = api_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 1,
        }, format='json')
        token = res1['X-Cart-Token']
        api_client.credentials(HTTP_X_CART_TOKEN=token)
        res2 = api_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 2,
        }, format='json')
        assert res2.status_code == 201
        assert res2.json()['quantity'] == 3  # 1 + 2

    def test_stock_insuficiente_retorna_400(
        self, api_client, product_sin_variante, db
    ):
        product_sin_variante.stock = 2
        product_sin_variante.save()
        res = api_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 5,
        }, format='json')
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'STOCK_INSUFICIENTE'

    def test_anonimo_recibe_cart_token_en_header(
        self, api_client, product_sin_variante, db
    ):
        res = api_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 1,
        }, format='json')
        assert 'X-Cart-Token' in res

    def test_autenticado_no_requiere_cart_token(
        self, auth_client, product_sin_variante, db
    ):
        res = auth_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 1,
        }, format='json')
        assert res.status_code == 201


# =============================================================================
# UC-CART-02 — Ver carrito con totales
# =============================================================================

class TestVerCarrito:

    def test_carrito_vacio_retorna_200(self, api_client, db):
        res = api_client.get(CART_URL)
        assert res.status_code == 200
        assert res.json()['items'] == []

    def test_carrito_incluye_totales(
        self, anon_client_with_cart, product_sin_variante, db
    ):
        client, _ = anon_client_with_cart
        res = client.get(CART_URL)
        data = res.json()
        assert 'totals' in data
        totals = data['totals']
        assert 'subtotal' in totals
        assert 'total' in totals

    def test_price_changed_detecta_cambio(
        self, anon_client_with_cart, product_sin_variante, db
    ):
        """FR-CART-01.02 Escenario 3: precio cambia entre sesiones."""
        client, _ = anon_client_with_cart
        # Cambiar el precio
        product_sin_variante.price = Decimal('950.00')
        product_sin_variante.save()
        res = client.get(CART_URL)
        item = res.json()['items'][0]
        assert item['price_changed'] is True

    def test_editar_cantidad_item(
        self, anon_client_with_cart, product_sin_variante, db
    ):
        client, _ = anon_client_with_cart
        cart_data = client.get(CART_URL).json()
        item_id = cart_data['items'][0]['id']
        res = client.patch(f'{ITEMS_URL}{item_id}/', {'quantity': 3}, format='json')
        assert res.status_code == 200
        assert res.json()['quantity'] == 3

    def test_editar_cantidad_mayor_al_stock_retorna_400(
        self, anon_client_with_cart, product_sin_variante, db
    ):
        product_sin_variante.stock = 2
        product_sin_variante.save()
        client, _ = anon_client_with_cart
        cart_data = client.get(CART_URL).json()
        item_id = cart_data['items'][0]['id']
        res = client.patch(f'{ITEMS_URL}{item_id}/', {'quantity': 5}, format='json')
        assert res.status_code == 400


# =============================================================================
# UC-CART-03 — Eliminar item del carrito
# =============================================================================

class TestEliminarItem:

    def test_eliminar_item_retorna_204(
        self, anon_client_with_cart, db
    ):
        client, _ = anon_client_with_cart
        cart_data = client.get(CART_URL).json()
        item_id = cart_data['items'][0]['id']
        res = client.delete(f'{ITEMS_URL}{item_id}/')
        assert res.status_code == 204

    def test_eliminar_item_actualiza_carrito(
        self, anon_client_with_cart, db
    ):
        client, _ = anon_client_with_cart
        cart_data = client.get(CART_URL).json()
        item_id = cart_data['items'][0]['id']
        client.delete(f'{ITEMS_URL}{item_id}/')
        cart_after = client.get(CART_URL).json()
        assert len(cart_after['items']) == 0

    def test_eliminar_item_de_otro_carrito_retorna_404(
        self, api_client, product_sin_variante, db
    ):
        """No se puede eliminar un item de otro carrito."""
        from apps.cart.models import Cart, CartItem
        other_cart = Cart.objects.create(cart_token=uuid.uuid4())
        item = CartItem.objects.create(
            cart=other_cart, product=product_sin_variante,
            quantity=1, unit_price=product_sin_variante.price,
        )
        # api_client tiene su propio carrito (vacío)
        api_client.post(ITEMS_URL, {'product_id': product_sin_variante.pk}, format='json')
        # Intentar borrar item del otro carrito → 404
        res = api_client.delete(f'{ITEMS_URL}{item.pk}/')
        assert res.status_code == 404

    def test_vaciar_carrito(self, anon_client_with_cart, db):
        client, _ = anon_client_with_cart
        res = client.delete(CART_URL)
        assert res.status_code == 204
        cart_data = client.get(CART_URL).json()
        assert len(cart_data['items']) == 0


# =============================================================================
# UC-CART-05 — Guardar carrito para después
# =============================================================================

class TestGuardarCarrito:

    def test_guardar_carrito_requiere_auth(self, api_client, db):
        res = api_client.post(SAVE_URL)
        assert res.status_code == 401

    def test_guardar_carrito_vacio_retorna_400(self, auth_client, db):
        res = auth_client.post(SAVE_URL)
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'CARRITO_VACIO'

    def test_guardar_carrito_con_items(
        self, auth_client, product_sin_variante, db
    ):
        auth_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 2,
        }, format='json')
        res = auth_client.post(SAVE_URL)
        assert res.status_code == 200
        assert res.json()['saved_count'] == 1

    def test_guardar_reemplaza_carrito_guardado_anterior(
        self, auth_client, product_sin_variante, db
    ):
        from apps.cart.models import SavedCart
        auth_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 1,
        }, format='json')
        auth_client.post(SAVE_URL)
        auth_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 3,
        }, format='json')
        auth_client.post(SAVE_URL)
        from apps.users.models import User
        user = User.objects.get(username='testuser')
        saved = SavedCart.objects.get(user=user)
        assert saved.items.count() == 1


# =============================================================================
# UC-CART-06 — Fusionar carrito anónimo al autenticar
# =============================================================================

class TestFusionarCarrito:

    def test_merge_sin_auth_retorna_401(self, api_client, db):
        res = api_client.post(MERGE_URL, {'cart_token': str(uuid.uuid4())}, format='json')
        assert res.status_code == 401

    def test_merge_fusiona_carrito_anonimo_en_usuario(
        self, auth_client, product_sin_variante, db
    ):
        """FC-CART-06 Escenario principal: fusión de carrito anónimo."""
        import uuid
        from apps.cart.models import Cart, CartItem
        # Crear carrito anónimo directamente en BD
        anon_token = uuid.uuid4()
        anon_cart = Cart.objects.create(cart_token=anon_token, user=None)
        CartItem.objects.create(
            cart=anon_cart, product=product_sin_variante,
            quantity=2, unit_price=product_sin_variante.price,
        )
        # Fusionar al autenticar
        merge_res = auth_client.post(MERGE_URL, {
            'cart_token': str(anon_token),
        }, format='json')
        assert merge_res.status_code == 200
        items = merge_res.json()['items']
        assert len(items) == 1
        assert items[0]['quantity'] == 2

    
    def test_merge_suma_cantidades_si_mismo_producto(
        self, auth_client, product_sin_variante, db
    ):
        """El usuario ya tenía 1 item; el anónimo tenía 2 del mismo → total 3."""
        import uuid
        from apps.cart.models import Cart, CartItem
        # El auth_client agrega 1 item propio
        auth_client.post(ITEMS_URL, {
            'product_id': product_sin_variante.pk, 'quantity': 1,
        }, format='json')
        # Carrito anónimo con 2 items — creado directamente en BD
        anon_token = uuid.uuid4()
        anon_cart = Cart.objects.create(cart_token=anon_token, user=None)
        CartItem.objects.create(
            cart=anon_cart, product=product_sin_variante,
            quantity=2, unit_price=product_sin_variante.price,
        )
        # Fusionar: total debe ser 1 + 2 = 3
        merge_res = auth_client.post(MERGE_URL, {
            'cart_token': str(anon_token),
        }, format='json')
        assert merge_res.status_code == 200
        items = merge_res.json()['items']
        assert len(items) == 1
        assert items[0]['quantity'] == 3

    
    def test_merge_con_token_inexistente_retorna_carrito_usuario(
        self, auth_client, db
    ):
        """Si el token no existe, se retorna el carrito del usuario sin error."""
        res = auth_client.post(MERGE_URL, {
            'cart_token': str(uuid.uuid4()),
        }, format='json')
        assert res.status_code == 200


# =============================================================================
# H-S12-006 — Protección de variante con CartItems (TODO cerrado de Sprint 9)
# =============================================================================

class TestProteccionVarianteConCartItems:

    def test_desactivar_variante_con_cart_items_retorna_400(
        self, admin_client, product_con_variante, variant_s12, db
    ):
        """H-S12-006: variante con CartItems activos no puede desactivarse."""
        from apps.cart.models import Cart, CartItem
        cart = Cart.objects.create(cart_token=uuid.uuid4())
        CartItem.objects.create(
            cart=cart, product=product_con_variante,
            variant=variant_s12, quantity=1,
            unit_price=variant_s12.effective_price(),
        )
        res = admin_client.delete(
            f'/api/v1/admin/products/{product_con_variante.pk}/variants/{variant_s12.pk}/'
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'VARIANTE_CON_ITEMS_EN_CARRITO'

    def test_desactivar_variante_sin_cart_items_ok(
        self, admin_client, product_con_variante, variant_s12, db
    ):
        res = admin_client.delete(
            f'/api/v1/admin/products/{product_con_variante.pk}/variants/{variant_s12.pk}/'
        )
        assert res.status_code == 204
