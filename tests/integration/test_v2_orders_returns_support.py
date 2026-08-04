"""
Tests de integracion — API v2 F3: orders, reviews, support

Verifica que los endpoints /api/v2/ para el bloque F3 son funcionales:
  - orders:    cancellations/ y GET de la coleccion
  - reviews:   PATCH sin /edit/, admin status/ y helpful-votes
  - support:   PATCH tickets/<id>/status/

Cuatro bloques del F3 original se retiraron tras medir la referencia
(odoo-tools@622ddc2a); cada uno deja su medicion inline donde estaba:
devoluciones y Q&A de producto (no existen en la referencia, sin analisis
que los sustente), y direccion/transportista/POST-de-orden (existen, pero
sobre el carrito, no sobre la orden).
"""
import pytest
from addons.helpdesk.models import SupportTicket

pytestmark = pytest.mark.integration

# ─── URLs v2 ────────────────────────────────────────────────────────────────
V2_ORDERS_BASE          = '/api/v2/orders/'
V2_PRODUCTS_BASE        = '/api/v2/products/'
V2_ADMIN_REVIEWS_BASE   = '/api/v2/admin/reviews/'
V2_SUPPORT_BASE         = '/api/v2/support/tickets/'

# ─── URLs v1 (dual-run) ──────────────────────────────────────────────────────
V1_ORDER_CANCEL_URL         = '/api/v2/orders/{n}/cancellations/'
V1_REVIEW_EDIT_URL          = '/api/v2/products/{pid}/reviews/{pk}/'
V1_SUPPORT_CLOSE_URL        = '/api/v2/support/tickets/{id}/status/'


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def ticket(db, user):
    return SupportTicket.objects.create(
        user=user,
        subject='Ticket de prueba F3',
        body='Tengo un problema con mi pedido',
    )


@pytest.fixture
def closed_ticket(db, user):
    return SupportTicket.objects.create(
        user=user,
        subject='Ticket cerrado F3',
        body='Problema resuelto',
        status=SupportTicket.Status.CLOSED,
    )


# ─── Orders Tier A ──────────────────────────────────────────────────────────

class TestOrderCancellationsV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ORDERS_BASE + 'ORD-0001/cancellations/'
        r = api_client.post(url, {})
        assert r.status_code == 401

    def test_v1_cancel_still_works(self, api_client):
        url = V1_ORDER_CANCEL_URL.format(n='ORD-0001')
        r = api_client.post(url, {})
        assert r.status_code == 401


# ─── Dirección y transportista — RETIRADOS: la referencia los pone en el
#     carrito, no en la orden ─────────────────────────────────────────────────
#
# ``orders/<n>/shipping-address/`` y ``orders/<n>/shipping-method/`` afirman una
# forma que la referencia contradice. Medido sobre ``odoo-tools@622ddc2a``:
#
# - ``odoo19c: addons/website_sale/controllers/main.py:1494-1499`` —
#   ``shop_update_address`` arranca con ``if not (order_sudo := request.cart)``:
#   opera **el carrito en sesión**, no una orden identificada por número.
# - ``odoo19c: addons/website_sale/controllers/delivery.py:34`` —
#   ``/shop/set_delivery_method``, mismo patrón sobre el carrito.
#
# No hay en todo el árbol una mutación de dirección o transportista sobre una
# orden ya confirmada: una vez confirmada, esos datos son del documento. La
# forma correcta es ``carrito → dirección → transportista → confirmar``, y su
# puerto es T-006/T-008 de la iniciativa ``crear-website-sale-raiz-escaparate``,
# que trae sus propios tests contra la forma de la referencia. Mantener estos
# dos aquí perpetuaba la forma vieja como si fuera el objetivo.


# ─── Returns — RETIRADA, la referencia no expone una devolución al cliente ───
#
# ``/api/v2/return-requests/`` y ``/api/v2/admin/return-requests/<id>/status/``
# no existen y **no se crean en este pase**. Medido sobre
# ``odoo-tools@622ddc2a``: en ``odoo19c:`` la única ``@route`` con ``return``
# en el path es ``sale_stock/controllers/portal.py:40``, y sirve el **PDF** de
# la etiqueta de una devolución ya creada. La devolución en sí es un
# **wizard de backoffice** — ``stock.return.picking``
# (``odoo19c: addons/stock/wizard/stock_picking_return.py:87``) — que opera un
# operador de almacén, no el comprador.
#
# Una solicitud de devolución self-service sería forma propia, y **no hay
# análisis que la sustente**: 0 documentos ``*return*``/``*devolucion*`` en
# ``pm/api/iniciativas/``. Inventarla aquí violaría la directiva vigente
# ("si no tienen análisis, no crees"). Cuando se decida, el hogar natural es
# la familia ``stock``, sobre el wizard portado.


# ─── Reviews Tier B ─────────────────────────────────────────────────────────

class TestReviewDetailV2:
    def test_patch_without_edit_suffix_returns_401(self, api_client):
        url = V2_PRODUCTS_BASE + '1/reviews/1/'
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401

    def test_v1_edit_url_still_works(self, api_client):
        url = V1_REVIEW_EDIT_URL.format(pid=1, pk=1)
        r = api_client.patch(url, {}, content_type='application/json')
        assert r.status_code == 401


class TestAdminReviewStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_ADMIN_REVIEWS_BASE + '1/status/'
        r = api_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 401

    def test_non_admin_returns_403(self, auth_client):
        url = V2_ADMIN_REVIEWS_BASE + '1/status/'
        r = auth_client.patch(url, {'action': 'approve'}, content_type='application/json')
        assert r.status_code == 403

    def test_invalid_action_returns_400(self, admin_auth_client):
        url = V2_ADMIN_REVIEWS_BASE + '999/status/'
        r = admin_auth_client.patch(url, {'action': 'delete'}, content_type='application/json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'


# ─── Q&A de producto — RETIRADA, no existe en la referencia ──────────────────
#
# ``/api/v2/admin/questions/<id>/{answers,status}/`` no existe y **no se crea
# en este pase**. Medido sobre ``odoo-tools@622ddc2a``: en ``odoo19c:`` hay
# **0** addons con ``question`` en el nombre y **0** ``@route`` con
# ``question`` en el path. El canal de preguntas de un comprador sobre un
# producto simplemente no está en el producto de referencia.
#
# Sería forma propia, y su decisión está abierta como trabajo aparte (Q&A y
# referidos). Sin análisis que la sustente, no se inventa aquí.


# ─── Support Tier B ─────────────────────────────────────────────────────────

class TestSupportTicketStatusV2:
    def test_unauthenticated_returns_401(self, api_client):
        url = V2_SUPPORT_BASE + '1/status/'
        r = api_client.patch(url, {'action': 'close'}, content_type='application/json')
        assert r.status_code == 401

    def test_invalid_action_returns_400(self, auth_client, ticket):
        url = V2_SUPPORT_BASE + f'{ticket.pk}/status/'
        r = auth_client.patch(url, {'action': 'delete'}, content_type='application/json')
        assert r.status_code == 400
        assert r.data['codigo_error'] == 'INVALID_ACTION'

    def test_close_ticket(self, auth_client, ticket):
        url = V2_SUPPORT_BASE + f'{ticket.pk}/status/'
        r = auth_client.patch(url, {'action': 'close'}, content_type='application/json')
        assert r.status_code == 200
        ticket.refresh_from_db()
        assert ticket.status == SupportTicket.Status.CLOSED

    def test_reopen_ticket(self, auth_client, closed_ticket):
        url = V2_SUPPORT_BASE + f'{closed_ticket.pk}/status/'
        r = auth_client.patch(url, {'action': 'reopen'}, content_type='application/json')
        assert r.status_code == 200
        closed_ticket.refresh_from_db()
        assert closed_ticket.status == SupportTicket.Status.OPEN

    def test_v1_close_still_works(self, api_client, ticket):
        url = V1_SUPPORT_CLOSE_URL.format(id=ticket.pk)
        r = api_client.post(url, {})
        assert r.status_code == 401


# ─── Orders v2 — GET list ────────────────────────────────────────────────────
#
# El ``POST`` a la colección se retira: **una orden no se crea posteando a
# ``/orders/``**. Medido sobre ``odoo-tools@622ddc2a``, el carrito *es* la
# orden en borrador — ``odoo19c: addons/website_sale/models/sale_order.py:133``
# filtra por ``Domain('state', '=', 'draft')`` para localizarlo, y las 6
# ``@route`` de ``controllers/cart.py`` la materializan al añadir la primera
# línea. El checkout no crea nada: **confirma** lo que ya existe.
#
# El 405 que devuelve hoy ``OrderListView`` es, por tanto, la respuesta
# correcta, no una brecha. Los dos tests que esperaban 400 afirmaban la forma
# contraria. El puerto del carrito es T-006 de
# ``crear-website-sale-raiz-escaparate``.


class TestOrderCollectionV2:

    def test_get_list_requires_auth(self, api_client):
        r = api_client.get(V2_ORDERS_BASE)
        assert r.status_code == 401

    def test_get_list_authenticated_returns_200(self, auth_client, db):
        r = auth_client.get(V2_ORDERS_BASE)
        assert r.status_code == 200

    def test_v1_orders_list_still_works(self, auth_client, db):
        r = auth_client.get('/api/v2/orders/')
        assert r.status_code == 200


# ─── Reviews v2 — helpful-votes (GAP-I2) ─────────────────────────────────────

V1_HELPFUL_URL = '/api/v2/products/{pid}/reviews/{pk}/helpful-votes/'
V2_HELPFUL_VOTES_URL = '/api/v2/products/{pid}/reviews/{pk}/helpful-votes/'


class TestReviewHelpfulVotesV2:

    def test_v2_url_resolves_and_requires_auth(self, api_client):
        r = api_client.post(V2_HELPFUL_VOTES_URL.format(pid=1, pk=1), {})
        assert r.status_code == 401

    def test_v1_helpful_still_works(self, api_client):
        r = api_client.post(V1_HELPFUL_URL.format(pid=1, pk=1), {})
        assert r.status_code == 401
