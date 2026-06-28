"""
Tests de integración — Schema OpenAPI (drf-spectacular)

Sprint 1: verifica que /api/schema/ funciona y tiene estructura válida.
Sprint 4 (T-001..T-008): verifica que cada grupo de endpoints aparece
            en el schema generado. pytest.mark.schema para estas clases.

DEC-SCHEMA-01: una clase por grupo de apps.
DEC-SCHEMA-02: cobertura representativa, no exhaustiva.
DEC-SCHEMA-03: nuevas clases usan pytest.mark.schema.
DEC-SCHEMA-05: hallazgos de paths ausentes documentados en
               analisis-cobertura-openapi-schema.rst.
"""
import pytest

pytestmark = pytest.mark.api


# =============================================================================
# Sprint 1 — tests originales
# =============================================================================

class TestSchemaEndpoint:
    """El endpoint /api/schema/ genera OpenAPI 3.0 válido."""

    def test_schema_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/')
        assert r.status_code == 200

    def test_schema_contiene_claves_openapi(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        data = r.json()
        assert 'openapi' in data
        assert 'info' in data
        assert 'paths' in data

    def test_schema_version_correcta(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        assert r.json()['info']['version'] == '1.0.0'

    def test_schema_titulo_correcto(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        assert 'PracticaYoruba' in r.json()['info']['title']

    def test_schema_contiene_endpoints_auth(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        paths = r.json()['paths']
        assert '/api/v1/auth/login/' in paths
        assert '/api/v1/auth/register/' in paths
        assert '/api/v1/auth/logout/' in paths

    def test_schema_contiene_endpoint_config(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        paths = r.json()['paths']
        assert '/api/v2/config/settings/' in paths

    def test_schema_register_tiene_request_body(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        register = r.json()['paths']['/api/v1/auth/register/']['post']
        assert 'requestBody' in register

    def test_schema_config_settings_patch_tiene_request(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        settings = r.json()['paths']['/api/v2/config/settings/']['patch']
        assert 'requestBody' in settings

    def test_schema_tiene_esquema_jwt(self, api_client, db):
        r = api_client.get('/api/schema/?format=json')
        schemas = r.json().get('components', {}).get('securitySchemes', {})
        assert 'jwtAuth' in schemas


class TestSwaggerUI:
    """La Swagger UI responde correctamente."""

    def test_swagger_ui_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/swagger-ui/')
        assert r.status_code == 200


class TestRedocUI:
    """La Redoc UI responde correctamente."""

    def test_redoc_retorna_200(self, api_client, db):
        r = api_client.get('/api/schema/redoc/')
        assert r.status_code == 200


# =============================================================================
# Sprint 4 — T-001..T-008 (pytest.mark.schema)
# =============================================================================

class TestSchemaAuthExtended:
    """
    T-001: Endpoints de auth Sprint 2/3 presentes en schema.

    H-SCHEMA-01: AddressViewSet usa DefaultRouter con basename='address'.
    El router genera /api/v1/auth/addresses/ (plural), no /api/v1/auth/address/.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_profile_en_schema(self, api_client, db):
        assert '/api/v1/auth/profile/' in self._paths(api_client, db)

    def test_addresses_en_schema(self, api_client, db):
        # H-SCHEMA-01: plural 'addresses' — generado por DefaultRouter
        assert '/api/v1/auth/addresses/' in self._paths(api_client, db)

    def test_address_detail_en_schema(self, api_client, db):
        assert '/api/v1/auth/addresses/{id}/' in self._paths(api_client, db)

    def test_change_password_en_schema(self, api_client, db):
        assert '/api/v1/auth/change-password/' in self._paths(api_client, db)

    def test_logout_all_en_schema(self, api_client, db):
        assert '/api/v1/auth/logout-all/' in self._paths(api_client, db)

    def test_verify_email_en_schema(self, api_client, db):
        assert '/api/v1/auth/verify-email/' in self._paths(api_client, db)

    def test_resend_verification_en_schema(self, api_client, db):
        assert '/api/v1/auth/resend-verification/' in self._paths(api_client, db)

    def test_password_reset_en_schema(self, api_client, db):
        assert '/api/v1/auth/password-reset/' in self._paths(api_client, db)

    def test_me_deactivate_en_schema(self, api_client, db):
        assert '/api/v1/auth/me/deactivate/' in self._paths(api_client, db)


class TestSchemaCartWishlist:
    """
    T-002: Endpoints de carrito y wishlist presentes en schema.

    Cart: CartView, CartItemListView, CartItemDetailView,
          CartSaveView, CartMergeView, CartVoucherView.
    Wishlist: WishlistView, WishlistItemDetailView, WishlistMoveToCartView.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_cart_en_schema(self, api_client, db):
        assert '/api/v2/cart/' in self._paths(api_client, db)

    def test_cart_items_en_schema(self, api_client, db):
        assert '/api/v2/cart/items/' in self._paths(api_client, db)

    def test_cart_item_detail_en_schema(self, api_client, db):
        assert '/api/v2/cart/items/{id}/' in self._paths(api_client, db)

    def test_cart_voucher_en_schema(self, api_client, db):
        assert '/api/v2/cart/voucher/' in self._paths(api_client, db)

    def test_wishlist_en_schema(self, api_client, db):
        assert '/api/v2/wishlist/' in self._paths(api_client, db)

    def test_wishlist_item_en_schema(self, api_client, db):
        assert '/api/v2/wishlist/{id}/' in self._paths(api_client, db)

    def test_wishlist_move_to_cart_en_schema(self, api_client, db):
        assert '/api/v2/wishlist/{id}/move-to-cart/' in self._paths(api_client, db)


class TestSchemaOrdersPayments:
    """
    T-003: Endpoints de órdenes y pagos presentes en schema.

    H-SCHEMA-02: El checkout principal (UC-ORD-01) está en
    /api/v2/orders/checkout/ (apps.orders.urls). El prefijo
    /api/v2/checkout/ corresponde a apps.payments.checkout_urls
    que solo tiene eligibility y express (UC-ORD-01-EXT, M-10).

    Orders usan <str:order_number> — schema genera {order_number}.
    Payments usan <str:order_number> — schema genera {order_number}.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_orders_list_en_schema(self, api_client, db):
        assert '/api/v2/orders/' in self._paths(api_client, db)

    def test_orders_checkout_en_schema(self, api_client, db):
        # H-SCHEMA-02: checkout principal en /api/v2/orders/checkout/
        assert '/api/v2/orders/checkout/' in self._paths(api_client, db)

    def test_orders_detail_en_schema(self, api_client, db):
        assert '/api/v2/orders/{order_number}/' in self._paths(api_client, db)

    def test_orders_cancel_en_schema(self, api_client, db):
        assert '/api/v2/orders/{order_number}/cancellations/' in self._paths(api_client, db)

    def test_checkout_express_en_schema(self, api_client, db):
        # H-SCHEMA-02: checkout express en /api/v2/checkout/ (M-10)
        assert '/api/v2/checkout/express/' in self._paths(api_client, db)

    def test_payments_initiate_en_schema(self, api_client, db):
        # Legacy initiate (redirect flow) stays on v1 until v1 sunset
        assert '/api/v1/payments/initiate/' in self._paths(api_client, db)

    def test_payments_status_en_schema(self, api_client, db):
        assert '/api/v2/payments/{order_number}/status/' in self._paths(api_client, db)

    def test_payments_history_en_schema(self, api_client, db):
        assert '/api/v2/payments/{order_number}/history/' in self._paths(api_client, db)


class TestSchemaCatalogue:
    """
    T-004: Endpoints de catálogo presentes en schema.

    H-SCHEMA-03: Hay dos endpoints 'categories':
    - /api/v1/categories/ — CategoryTreeView (browse_public_urls, montado en api/v1/)
    - /api/v2/catalogue/categories/ — CategoryListView (catalogue/urls.py)
    Ambos son válidos y coexisten; se verifican los dos.

    browse_public_urls también provee /api/v2/catalogue/search/
    (CatalogueSearchView, wrapper P-17 con normalized_query).
    catalogue/urls.py provee /api/v2/catalogue/search/
    (ProductSearchView, versión legacy). drf-spectacular puede
    colapsar ambos en una sola entrada o mostrar la primera únicamente.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_catalogue_list_en_schema(self, api_client, db):
        assert '/api/v2/catalogue/' in self._paths(api_client, db)

    def test_catalogue_search_en_schema(self, api_client, db):
        assert '/api/v2/catalogue/search/' in self._paths(api_client, db)

    def test_catalogue_product_detail_en_schema(self, api_client, db):
        assert '/api/v2/catalogue/{slug}/' in self._paths(api_client, db)

    def test_categories_browse_en_schema(self, api_client, db):
        # H-SCHEMA-03: CategoryTreeView en /api/v1/categories/ (browse_public)
        assert '/api/v2/catalogue/categories/tree/' in self._paths(api_client, db)

    def test_product_related_en_schema(self, api_client, db):
        assert '/api/v1/products/{slug}/related/' in self._paths(api_client, db)

    def test_catalogue_autocomplete_en_schema(self, api_client, db):
        assert '/api/v2/catalogue/autocomplete/' in self._paths(api_client, db)


class TestSchemaReviewsQuestions:
    """
    T-005: Endpoints de reviews, preguntas e historial de búsqueda.

    Todos montados bajo /api/v1/products/ con product_id int.
    Search history montado bajo /api/v2/search/.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_product_reviews_en_schema(self, api_client, db):
        assert '/api/v2/products/{product_id}/reviews/' in self._paths(api_client, db)

    def test_product_review_helpful_en_schema(self, api_client, db):
        assert '/api/v2/products/{product_id}/reviews/{id}/helpful/' in self._paths(api_client, db)

    def test_product_questions_en_schema(self, api_client, db):
        assert '/api/v2/products/{product_id}/questions/' in self._paths(api_client, db)

    def test_search_history_en_schema(self, api_client, db):
        assert '/api/v2/search/history/' in self._paths(api_client, db)

    def test_search_history_detail_en_schema(self, api_client, db):
        assert '/api/v2/search/history/{id}/' in self._paths(api_client, db)


class TestSchemaInventoryLogisticsVoucher:
    """
    T-006: Endpoints de inventario, logística y vouchers.

    Inventory montado en /api/v2/admin/inventory/ (apps.inventory.urls).
    Logistics montado en /api/v2/logistics/ (apps.logistics.urls).
    Voucher router montado en /api/v2/admin/vouchers/ (apps.voucher.urls).
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_inventory_dashboard_en_schema(self, api_client, db):
        assert '/api/v2/admin/inventory/' in self._paths(api_client, db)

    def test_inventory_alerts_en_schema(self, api_client, db):
        assert '/api/v2/admin/inventory/alerts/' in self._paths(api_client, db)

    def test_logistics_panel_en_schema(self, api_client, db):
        assert '/api/v2/logistics/' in self._paths(api_client, db)

    def test_logistics_guides_en_schema(self, api_client, db):
        assert '/api/v2/logistics/guides/' in self._paths(api_client, db)

    def test_logistics_confirm_delivery_en_schema(self, api_client, db):
        assert '/api/v2/logistics/guides/{id}/confirm-delivery/' in self._paths(api_client, db)

    def test_vouchers_list_en_schema(self, api_client, db):
        assert '/api/v2/admin/vouchers/' in self._paths(api_client, db)

    def test_voucher_detail_en_schema(self, api_client, db):
        assert '/api/v2/admin/vouchers/{id}/' in self._paths(api_client, db)


class TestSchemaSupportReturnsNewsletter:
    """
    T-007: Endpoints de soporte, devoluciones, contacto, newsletter
    y notificaciones.

    H-SCHEMA-04: Contact endpoint es /api/v2/contact/messages/
    (ContactMessageCreateView con path 'messages/'), NO /api/v2/contact/.

    H-SCHEMA-05: Newsletter confirm token en path variable:
    /api/v2/newsletter/confirm/{token}/ (str param).
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_support_tickets_en_schema(self, api_client, db):
        assert '/api/v2/support/tickets/' in self._paths(api_client, db)

    def test_support_ticket_close_en_schema(self, api_client, db):
        assert '/api/v2/support/tickets/{ticket_id}/close/' in self._paths(api_client, db)

    def test_returns_en_schema(self, api_client, db):
        assert '/api/v2/return-requests/' in self._paths(api_client, db)

    def test_returns_detail_en_schema(self, api_client, db):
        assert '/api/v2/return-requests/{return_id}/' in self._paths(api_client, db)

    def test_contact_messages_en_schema(self, api_client, db):
        # H-SCHEMA-04: path es /messages/ dentro de /api/v2/contact/
        assert '/api/v2/contact/messages/' in self._paths(api_client, db)

    def test_newsletter_subscribe_en_schema(self, api_client, db):
        assert '/api/v2/newsletter/subscribe/' in self._paths(api_client, db)

    def test_newsletter_confirm_en_schema(self, api_client, db):
        # H-SCHEMA-05: token es path param str
        assert '/api/v2/newsletter/confirm/{token}/' in self._paths(api_client, db)

    def test_notifications_en_schema(self, api_client, db):
        assert '/api/v2/notifications/' in self._paths(api_client, db)


class TestSchemaAdminEndpoints:
    """
    T-008: Endpoints admin representativos de cada dominio.

    Users admin usa DefaultRouter (AdminUserViewSet) — genera
    /api/v2/admin/users/ y /api/v2/admin/users/{id}/.
    Las custom actions (suspend, reactivate, make-admin) generan
    /api/v2/admin/users/{id}/suspend/ etc. si el ViewSet las declara.
    Orders admin usa <str:order_number> — schema genera {order_number}.
    """
    pytestmark = pytest.mark.schema

    def _paths(self, api_client, db):
        return api_client.get('/api/schema/?format=json').json()['paths']

    def test_admin_users_en_schema(self, api_client, db):
        assert '/api/v2/admin/users/' in self._paths(api_client, db)

    def test_admin_user_detail_en_schema(self, api_client, db):
        assert '/api/v2/admin/users/{id}/' in self._paths(api_client, db)

    def test_admin_orders_en_schema(self, api_client, db):
        assert '/api/v2/admin/orders/' in self._paths(api_client, db)

    def test_admin_order_detail_en_schema(self, api_client, db):
        assert '/api/v2/admin/orders/{order_number}/' in self._paths(api_client, db)

    def test_admin_reviews_en_schema(self, api_client, db):
        assert '/api/v2/admin/reviews/' in self._paths(api_client, db)

    def test_admin_review_approve_en_schema(self, api_client, db):
        assert '/api/v2/admin/reviews/{id}/approve/' in self._paths(api_client, db)

    def test_admin_reports_sales_en_schema(self, api_client, db):
        assert '/api/v2/admin/reports/sales/' in self._paths(api_client, db)

    def test_admin_reports_dashboard_en_schema(self, api_client, db):
        assert '/api/v2/admin/reports/dashboard/' in self._paths(api_client, db)

    def test_admin_settings_en_schema(self, api_client, db):
        assert '/api/v2/admin/settings/' in self._paths(api_client, db)

    def test_admin_questions_en_schema(self, api_client, db):
        assert '/api/v2/admin/questions/' in self._paths(api_client, db)

    def test_admin_question_approve_en_schema(self, api_client, db):
        assert '/api/v2/admin/questions/{question_id}/approve/' in self._paths(api_client, db)

    def test_admin_dashboard_en_schema(self, api_client, db):
        assert '/api/v2/admin/dashboard/' in self._paths(api_client, db)
