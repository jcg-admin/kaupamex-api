"""
Integration tests — P-14 reviews endpoints (UC-REV-01..03).
"""
import io
from decimal import Decimal
from addons.catalogue.models import Category, Product
from addons.orders.models import Order, OrderAddress, OrderItem, OrderValue
from addons.rating.models import Review, ReviewHelpfulVote, ReviewModerationLog
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from PIL import Image as PILImage
from tests.factories.user_factory import make_buyer

import pytest
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration


PRODUCT_REVIEWS_URL = lambda pid: f'/api/v2/products/{pid}/reviews/'
ADMIN_QUEUE_URL     = '/api/v2/admin/reviews/'
APPROVE_URL         = lambda pk: f'/api/v2/admin/reviews/{pk}/status/'
REJECT_URL          = lambda pk: f'/api/v2/admin/reviews/{pk}/status/'
HELPFUL_URL         = lambda pid, pk: f'/api/v2/products/{pid}/reviews/{pk}/helpful-votes/'
EDIT_URL            = lambda pid, pk: f'/api/v2/products/{pid}/reviews/{pk}/'


# ─── Enforcement capacidad-dirigido (ADR-020, DEC-ENF-01: account.reviews) ───
class TestReviewsCapabilityGate:
    """Las acciones propias del comprador sobre reseñas (crear, editar, foto,
    voto útil) exigen ``account.reviews`` además de autenticación. Un usuario
    autenticado SIN esa capacidad recibe 403 (el ``GET`` de listado sigue
    público). En producción todo comprador la tiene (ADR-020)."""

    def _authed_without_capability(self, api_client):
        u = get_user_model().objects.create_user(
            email='norole-reviews@practicayoruba.mx', password='TestPass123!',
        )
        api_client.force_login(u)
        return u

    def test_create_review_requires_account_reviews(self, api_client, db):
        self._authed_without_capability(api_client)
        res = api_client.post(
            PRODUCT_REVIEWS_URL(999999),
            {'order_id': 1, 'rating': 5, 'title': 'x', 'body': 'y'},
            format='json',
        )
        assert res.status_code == 403

    def test_helpful_vote_requires_account_reviews(self, api_client, db):
        self._authed_without_capability(api_client)
        res = api_client.post(HELPFUL_URL(999999, 999999), format='json')
        assert res.status_code == 403

    def test_edit_review_requires_account_reviews(self, api_client, db):
        self._authed_without_capability(api_client)
        res = api_client.patch(
            EDIT_URL(999999, 999999), {'rating': 4}, format='json',
        )
        assert res.status_code == 403

    def test_public_listing_stays_open(self, api_client, prod_rev, db):
        # GET de listado NO exige capacidad (sigue público / AllowAny).
        res = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id))
        assert res.status_code == 200


@pytest.fixture
def cat_rev(db):
    return Category.objects.create(name='Rev', slug='rev', is_active=True)


@pytest.fixture
def prod_rev(db, cat_rev):
    _p = Product.objects.create(
        name='Producto Rev', slug='producto-rev', sku='REV-001',
        price=Decimal('100'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(cat_rev)
    return _p


@pytest.fixture
def order_user_with_product(db, user, prod_rev):
    o = make_order(user=user, status='DELIVERED')
    OrderItem.objects.create(
        order=o, product=prod_rev, product_name=prod_rev.name,
        sku=prod_rev.sku, unit_price=Decimal('100'),
        quantity=1, subtotal=Decimal('100'),
    )
    OrderValue.objects.create(
        order=o, subtotal=Decimal('100'), tax=Decimal('0'),
        shipping_cost=Decimal('0'), total=Decimal('100'),
    )
    OrderAddress.objects.create(
        order=o, recipient_name='X', street='Y', city='Z',
        state='Z', zip_code='00000',
    )
    return o


class TestPublicReviewListing:
    """UC-REV-01."""

    def test_listado_solo_aprobadas_con_metricas(
        self, api_client, prod_rev, user, order_user_with_product, db,
    ):
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='Buena', body='Excelente',
            status=Review.STATUS_APPROVED,
        )
        # Una pendiente que NO debe aparecer.
        u2 = get_user_model().objects.create_user(
            email='u2@rev.com', password='x',
        )
        o2 = make_order(user=u2, status='DELIVERED')
        Review.objects.create(
            user=u2, product=prod_rev, order=o2, sale_order=o2.sale_order,
            rating=2, title='Mala', body='Mala',
            status=Review.STATUS_PENDING,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id))
        assert r.status_code == 200
        data = r.json()
        assert data['total_reviews'] == 1
        assert data['average_rating'] == 5.0
        assert data['rating_breakdown']['5'] == 1
        assert len(data['results']) == 1

    def test_producto_inexistente_loud_404(self, api_client, db):
        r = api_client.get(PRODUCT_REVIEWS_URL(999999))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_FOUND'


class TestCreateReview:
    """UC-REV-02."""

    def test_comprador_crea_resena_201_pending(
        self, auth_client, prod_rev, order_user_with_product, db,
    ):
        r = auth_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {
            'order_id': order_user_with_product.id,
            'rating': 4, 'title': 'OK', 'body': 'OK',
        }, format='json')
        assert r.status_code == 201
        assert r.json()['status'] == 'PENDING_MODERATION'

    def test_403_si_orden_es_de_otro_usuario(
        self, auth_client, prod_rev, db,
    ):
        other = get_user_model().objects.create_user(
            email='or@rev.com', password='x',
        )
        o = make_order(user=other, status='DELIVERED')
        r = auth_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {
            'order_id': o.id, 'rating': 4, 'title': 'X', 'body': 'X',
        }, format='json')
        assert r.status_code == 403
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_PURCHASED'

    def test_403_si_orden_no_esta_DELIVERED(
        self, auth_client, user, prod_rev, db,
    ):
        """UC-REV-01 PRE-01 (T-118 D-01 CRITICA): solo se permite
        reseñar productos de ordenes ENTREGADAS. Antes cualquier
        estado pasaba el guard."""
        for st in ('PENDING', 'PROCESSING', 'SHIPPED'):
            o = make_order(user=user, status=st)
            OrderItem.objects.create(
                order=o, product=prod_rev, product_name=prod_rev.name,
                sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
                subtotal=Decimal('100'),
            )
            r = auth_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {
                'order_id': o.id, 'rating': 4,
                'title': f'pre-{st}', 'body': 'cuerpo de prueba',
            }, format='json')
            assert r.status_code == 403, (
                f'status={st} debio rechazar, recibio {r.status_code}'
            )
            assert r.json()['codigo_error'] == 'ORDER_NOT_DELIVERED'

    def test_409_resena_duplicada(
        self, auth_client, user, prod_rev, order_user_with_product, db,
    ):
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='A', body='B',
        )
        r = auth_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {
            'order_id': order_user_with_product.id,
            'rating': 3, 'title': 'C', 'body': 'D',
        }, format='json')
        # Aceptamos 400 con codigo_error REVIEW_DUPLICATE (DRF ValidationError).
        assert r.status_code in (400, 409)
        assert r.json()['codigo_error'] == 'REVIEW_DUPLICATE'

    def test_requiere_auth(self, api_client, prod_rev, db):
        r = api_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {}, format='json')
        assert r.status_code == 401


class TestAdminQueue:
    """UC-REV-03 — FIFO + idempotent approve/reject."""

    def test_queue_pending_fifo(
        self, admin_client, user, prod_rev, order_user_with_product, db,
    ):
        r1 = Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=3, title='1', body='1',
        )
        r = admin_client.get(ADMIN_QUEUE_URL + '?status=PENDING_MODERATION')
        assert r.status_code == 200
        ids = [row['id'] for row in r.json()['results']]
        assert r1.id in ids

    def test_approve_idempotente_y_audita(
        self, admin_client, user, prod_rev, order_user_with_product, db,
    ):
        rev = Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='1', body='1',
        )
        # Primera aprobacion.
        r = admin_client.patch(APPROVE_URL(rev.id), {'action': 'approve'}, format='json')
        assert r.status_code == 200
        assert r.json()['status'] == 'APPROVED'
        assert r.json()['already_approved'] is False
        # Segunda aprobacion — idempotente.
        r2 = admin_client.patch(APPROVE_URL(rev.id), {'action': 'approve'}, format='json')
        assert r2.status_code == 200
        assert r2.json()['already_approved'] is True
        # Audit log exactamente una entrada.
        assert ReviewModerationLog.objects.filter(
            review=rev,
            action=ReviewModerationLog.ACTION_APPROVE,
        ).count() == 1

    def test_reject_requiere_reason_y_audita(
        self, admin_client, user, prod_rev, order_user_with_product, db,
    ):
        rev = Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=1, title='no', body='no',
        )
        r = admin_client.patch(REJECT_URL(rev.id), {'action': 'reject', 'reason': 'SPAM'}, format='json')
        assert r.status_code == 200
        assert r.json()['status'] == 'REJECTED'
        assert r.json()['reject_reason'] == 'SPAM'
        assert ReviewModerationLog.objects.filter(
            review=rev,
            action=ReviewModerationLog.ACTION_REJECT,
        ).count() == 1

    def test_reject_reason_invalido_loud(
        self, admin_client, user, prod_rev, order_user_with_product, db,
    ):
        rev = Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=1, title='no', body='no',
        )
        r = admin_client.patch(REJECT_URL(rev.id), {'action': 'reject', 'reason': 'NOPE'}, format='json')
        assert r.status_code == 400
        # Canon EN (T-118 alineamiento + anti-soft-on-tests): codigo ya
        # retorna REASON_INVALID. Antes el test era outlier ES.
        assert r.json()['codigo_error'] == 'REASON_INVALID'

    def test_comprador_no_puede_aprobar(
        self, auth_client, user, prod_rev, order_user_with_product, db,
    ):
        rev = Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='ok', body='ok',
        )
        r = auth_client.patch(APPROVE_URL(rev.id), {'action': 'approve'}, format='json')
        assert r.status_code == 403


# =============================================================================
# T-118 — New capabilities: pagination, rating filter, helpful votes
# =============================================================================

class TestReviewPagination:
    """UC-REV-02 Gap P-20 — pagination + rating filter."""

    def test_respuesta_incluye_campos_paginacion(
        self, api_client, prod_rev, user, order_user_with_product, db,
    ):
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='T', body='B', status=Review.STATUS_APPROVED,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id))
        data = r.json()
        for field in ('count', 'page', 'pages', 'results'):
            assert field in data, f'campo faltante: {field}'

    def test_filtro_por_rating_filtra_resultados(
        self, api_client, prod_rev, user, order_user_with_product, db,
    ):
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='T5', body='B', status=Review.STATUS_APPROVED,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'rating': '5'})
        assert r.status_code == 200
        for rev in r.json()['results']:
            assert rev['rating'] == 5

    def test_filtro_rating_invalido_retorna_400(
        self, api_client, prod_rev, db,
    ):
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'rating': '9'})
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'RATING_INVALID'

    def test_sort_helpful_acepta_parametro(
        self, api_client, prod_rev, user, order_user_with_product, db,
    ):
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=4, title='T', body='B', status=Review.STATUS_APPROVED,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'sort': 'helpful'})
        assert r.status_code == 200


class TestReviewHelpfulVote:
    """UC-REV-02 FR-REV-02.02 — helpful votes."""

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='T', body='B', status=Review.STATUS_APPROVED,
        )

    def test_voto_incrementa_helpful_count(
        self, admin_auth_client, prod_rev, approved_review, db,
    ):
        r = admin_auth_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        assert r.status_code == 200
        approved_review.refresh_from_db()
        assert approved_review.helpful_count == 1

    def test_voto_retorna_helpful_count_actualizado(
        self, admin_auth_client, prod_rev, approved_review, db,
    ):
        r = admin_auth_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        assert r.json()['helpful_count'] == 1

    def test_voto_duplicado_retorna_400(
        self, admin_auth_client, prod_rev, approved_review, db,
    ):
        admin_auth_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        r = admin_auth_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'VOTE_DUPLICATE'

    def test_no_puede_votar_propia_resena(
        self, auth_client, prod_rev, approved_review, db,
    ):
        r = auth_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'CANNOT_VOTE_OWN_REVIEW'

    def test_requiere_autenticacion(
        self, api_client, prod_rev, approved_review, db,
    ):
        r = api_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        assert r.status_code == 401

    def test_helpful_count_aparece_en_public_listing(
        self, api_client, admin_auth_client, prod_rev, approved_review, db,
    ):
        admin_auth_client.post(
            HELPFUL_URL(prod_rev.id, approved_review.id), {}, format='json',
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id))
        review_data = r.json()['results'][0]
        assert 'helpful_count' in review_data
        assert review_data['helpful_count'] == 1


# =============================================================================
# P-21 — Gap coverage: ACs without test assertions
# =============================================================================

class TestRatingFilterAndSorting:
    """UC-REV-01 — rating filter excludes non-matching; helpful sort orders correctly."""

    def _make_order(self, db, user):
        o = make_order(user=user, status='DELIVERED')
        OrderValue.objects.create(
            order=o, subtotal=Decimal('100'), tax=Decimal('0'),
            shipping_cost=Decimal('0'), total=Decimal('100'),
        )
        OrderAddress.objects.create(
            order=o, recipient_name='X', street='Y', city='Z',
            state='Z', zip_code='00000',
        )
        return o

    def test_rating_filter_excludes_other_ratings(
        self, api_client, prod_rev, user, db,
    ):
        """Filter ?rating=3 must exclude reviews with rating != 3."""
        u2 = get_user_model().objects.create_user(
            email='uf2@rev.com', password='x',
        )
        o1 = self._make_order(db, user)
        OrderItem.objects.create(
            order=o1, product=prod_rev, product_name=prod_rev.name,
            sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        o2 = self._make_order(db, u2)
        Review.objects.create(
            user=user, product=prod_rev, order=o1, sale_order=o1.sale_order,
            rating=3, title='Tres', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        Review.objects.create(
            user=u2, product=prod_rev, order=o2, sale_order=o2.sale_order,
            rating=5, title='Cinco', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'rating': '3'})
        assert r.status_code == 200
        results = r.json()['results']
        assert len(results) == 1
        assert results[0]['rating'] == 3

    def test_sort_helpful_orders_by_helpful_count_desc(
        self, api_client, admin_auth_client, prod_rev, user, db,
    ):
        """?sort=helpful must put the review with more votes first."""
        u2 = get_user_model().objects.create_user(
            email='usort2@rev.com', password='x',
        )
        o1 = self._make_order(db, user)
        OrderItem.objects.create(
            order=o1, product=prod_rev, product_name=prod_rev.name,
            sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        o2 = self._make_order(db, u2)
        rev_low = Review.objects.create(
            user=user, product=prod_rev, order=o1, sale_order=o1.sale_order,
            rating=4, title='Low', body='cuerpo',
            status=Review.STATUS_APPROVED,
            helpful_count=0,
        )
        rev_high = Review.objects.create(
            user=u2, product=prod_rev, order=o2, sale_order=o2.sale_order,
            rating=5, title='High', body='cuerpo',
            status=Review.STATUS_APPROVED,
            helpful_count=5,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'sort': 'helpful'})
        assert r.status_code == 200
        results = r.json()['results']
        assert len(results) == 2
        assert results[0]['id'] == rev_high.id

    def test_pagination_second_page_slices_correctly(
        self, api_client, prod_rev, user, db,
    ):
        """Page 2 with page_size=1 should return the second-oldest approved review."""
        u2 = get_user_model().objects.create_user(
            email='upage2@rev.com', password='x',
        )
        o1 = self._make_order(db, user)
        OrderItem.objects.create(
            order=o1, product=prod_rev, product_name=prod_rev.name,
            sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        o2 = self._make_order(db, u2)
        rev1 = Review.objects.create(
            user=user, product=prod_rev, order=o1, sale_order=o1.sale_order,
            rating=4, title='First', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        rev2 = Review.objects.create(
            user=u2, product=prod_rev, order=o2, sale_order=o2.sale_order,
            rating=5, title='Second', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        r = api_client.get(
            PRODUCT_REVIEWS_URL(prod_rev.id), {'page_size': '1', 'page': '2'},
        )
        assert r.status_code == 200
        data = r.json()
        assert data['pages'] == 2
        assert len(data['results']) == 1

    def test_pagination_invalid_page_size_returns_400(
        self, api_client, prod_rev, db,
    ):
        r = api_client.get(
            PRODUCT_REVIEWS_URL(prod_rev.id), {'page_size': 'abc'},
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_PAGINATION'


class TestCreateReviewEdgeCases:
    """UC-REV-01/02 edge cases not covered by baseline tests."""

    def test_product_not_in_order_returns_403(
        self, auth_client, user, prod_rev, cat_rev, db,
    ):
        """Order is delivered but the reviewed product was not in it."""
        other_prod = Product.objects.create(
            name='Otro Prod', slug='otro-prod-p21', sku='REV-OTHER-01',
            price=Decimal('50'), stock=5,
            is_active=True, is_published=True,
        )
        other_prod.categories.add(cat_rev)
        other_prod.categories.add(cat_rev)
        o = make_order(user=user, status='DELIVERED')
        # order only contains other_prod, not prod_rev
        OrderItem.objects.create(
            order=o, product=other_prod, product_name=other_prod.name,
            sku=other_prod.sku, unit_price=Decimal('50'), quantity=1,
            subtotal=Decimal('50'),
        )
        OrderValue.objects.create(
            order=o, subtotal=Decimal('50'), tax=Decimal('0'),
            shipping_cost=Decimal('0'), total=Decimal('50'),
        )
        OrderAddress.objects.create(
            order=o, recipient_name='X', street='Y', city='Z',
            state='Z', zip_code='00000',
        )
        r = auth_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {
            'order_id': o.id, 'rating': 4, 'title': 'X', 'body': 'X',
        }, format='json')
        assert r.status_code == 403
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_PURCHASED'

    def test_order_not_found_returns_404(
        self, auth_client, prod_rev, db,
    ):
        r = auth_client.post(PRODUCT_REVIEWS_URL(prod_rev.id), {
            'order_id': 999999, 'rating': 4, 'title': 'X', 'body': 'X',
        }, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'ORDER_NOT_FOUND'


class TestAdminModerationGuards:
    """UC-REV-03 — state-machine guards not covered by baseline."""

    @pytest.fixture
    def pending_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=3, title='Pend', body='cuerpo',
            status=Review.STATUS_PENDING,
        )

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='Aprov', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )

    @pytest.fixture
    def rejected_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=1, title='Rej', body='cuerpo',
            status=Review.STATUS_REJECTED,
            reject_reason='SPAM',
        )

    def test_approve_rejected_review_returns_400(
        self, admin_client, rejected_review, db,
    ):
        """Cannot approve a review that was already rejected."""
        r = admin_client.patch(APPROVE_URL(rejected_review.id), {'action': 'approve'}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_ALREADY_REJECTED'

    def test_reject_approved_review_returns_400(
        self, admin_client, approved_review, db,
    ):
        """Cannot reject a review that was already approved."""
        r = admin_client.patch(
            REJECT_URL(approved_review.id), {'action': 'reject', 'reason': 'SPAM'}, format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_ALREADY_APPROVED'

    def test_approve_nonexistent_review_returns_404(
        self, admin_client, db,
    ):
        r = admin_client.patch(APPROVE_URL(999999), {'action': 'approve'}, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'REVIEW_NOT_FOUND'

    def test_reject_nonexistent_review_returns_404(
        self, admin_client, db,
    ):
        r = admin_client.patch(
            REJECT_URL(999999), {'action': 'reject', 'reason': 'SPAM'}, format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'REVIEW_NOT_FOUND'

    def test_admin_queue_invalid_status_returns_400(
        self, admin_client, db,
    ):
        r = admin_client.get(ADMIN_QUEUE_URL + '?status=INVALID_STATUS')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'STATUS_INVALID'

    def test_admin_queue_approved_status_returns_approved_only(
        self, admin_client, user, prod_rev, order_user_with_product, db,
    ):
        """?status=APPROVED queue returns only approved reviews."""
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='App', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        r = admin_client.get(ADMIN_QUEUE_URL + '?status=APPROVED')
        assert r.status_code == 200
        results = r.json()['results']
        assert all(rev['status'] == 'APPROVED' for rev in results)

    def test_reject_without_reason_returns_400(
        self, admin_client, pending_review, db,
    ):
        """Omitting reason entirely must return REASON_INVALID."""
        r = admin_client.patch(REJECT_URL(pending_review.id), {'action': 'reject'}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REASON_INVALID'

    def test_helpful_vote_on_nonexistent_review_returns_404(
        self, admin_auth_client, prod_rev, db,
    ):
        r = admin_auth_client.post(
            HELPFUL_URL(prod_rev.id, 999999), {}, format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'REVIEW_NOT_FOUND'


# =============================================================================
# UC-REV-01 Alt B — buyer edits their own pending review
# =============================================================================

class TestBuyerEditReview:
    """UC-REV-01 Alt B — PATCH edit endpoint for pending reviews."""

    @pytest.fixture
    def pending_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=3, title='Titulo original', body='Cuerpo original largo',
            status=Review.STATUS_PENDING,
        )

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='Aprobada', body='Cuerpo aprobado largo',
            status=Review.STATUS_APPROVED,
        )

    @pytest.fixture
    def rejected_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=1, title='Rechazada', body='Cuerpo rechazado largo',
            status=Review.STATUS_REJECTED,
            reject_reason='SPAM',
        )

    def test_buyer_can_edit_pending_review(
        self, auth_client, prod_rev, pending_review, db,
    ):
        """PATCH own pending review returns 200 with updated fields."""
        r = auth_client.patch(
            EDIT_URL(prod_rev.id, pending_review.id),
            {'rating': 5, 'title': 'Nuevo titulo', 'body': 'Cuerpo actualizado extenso'},
            format='json',
        )
        assert r.status_code == 200
        data = r.json()
        assert data['rating'] == 5
        assert data['title'] == 'Nuevo titulo'
        assert data['body'] == 'Cuerpo actualizado extenso'
        assert data['status'] == Review.STATUS_PENDING

        pending_review.refresh_from_db()
        assert pending_review.rating == 5
        assert pending_review.title == 'Nuevo titulo'

    def test_buyer_cannot_edit_other_users_review(
        self, api_client, prod_rev, db, order_user_with_product,
    ):
        """403 REVIEW_NOT_OWNER when editing another user's review."""
        other = get_user_model().objects.create_user(
            email='otheredit@rev.com', password='x',
        )
        o_other = make_order(user=other, status='DELIVERED')
        review = Review.objects.create(
            user=other, product=prod_rev, order=o_other, sale_order=o_other.sale_order,
            rating=2, title='Otro', body='Cuerpo de otro usuario largo',
            status=Review.STATUS_PENDING,
        )
        # Authenticate as a different user (re-use the `user` fixture via
        # creating a fresh user here and logging in manually).
        # El atacante es otro comprador (account.reviews) — pasa el candado de
        # capacidad y llega al owner-check, que devuelve REVIEW_NOT_OWNER.
        attacker = make_buyer(get_user_model().objects.create_user(
            email='attacker@rev.com', password='x',
        ))
        api_client.force_login(attacker)
        r = api_client.patch(
            EDIT_URL(prod_rev.id, review.id),
            {'rating': 5},
            format='json',
        )
        assert r.status_code == 403
        assert r.json()['codigo_error'] == 'REVIEW_NOT_OWNER'

    def test_buyer_cannot_edit_approved_review(
        self, auth_client, prod_rev, approved_review, db,
    ):
        """400 REVIEW_NOT_EDITABLE when review is APPROVED."""
        r = auth_client.patch(
            EDIT_URL(prod_rev.id, approved_review.id),
            {'rating': 4},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_NOT_EDITABLE'

    def test_buyer_cannot_edit_rejected_review(
        self, auth_client, prod_rev, rejected_review, db,
    ):
        """400 REVIEW_NOT_EDITABLE when review is REJECTED."""
        r = auth_client.patch(
            EDIT_URL(prod_rev.id, rejected_review.id),
            {'rating': 4},
            format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_NOT_EDITABLE'


IMAGES_URL = lambda pid, pk: f'/api/v2/products/{pid}/reviews/{pk}/images/'


def _make_png():
    """Return a minimal in-memory PNG as BytesIO (no Pillow required)."""
    buf = io.BytesIO()
    PILImage.new('RGB', (10, 10), color='red').save(buf, format='PNG')
    buf.seek(0)
    buf.name = 'test.png'
    return buf


class TestReviewImages:
    """UC-REV-02 cap6 — photos on reviews."""

    @pytest.fixture
    def pending_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='Great', body='Really great product',
            status=Review.STATUS_PENDING,
        )

    def test_add_image_to_review(self, auth_client, prod_rev, pending_review, db):
        """UC-REV-02 cap6: author can add image to own review."""
        res = auth_client.post(
            IMAGES_URL(prod_rev.id, pending_review.id),
            {'image': _make_png()},
            format='multipart',
        )
        assert res.status_code == 201
        data = res.json()
        assert 'id' in data
        assert 'image' in data

    def test_add_image_not_owner_returns_403(
        self, prod_rev, pending_review, api_client, db,
    ):
        """Non-owner cannot add image."""
        # Otro comprador (account.reviews) — pasa el candado y cae en el
        # owner-check (REVIEW_NOT_OWNER), no en el gate de capacidad.
        other = make_buyer(get_user_model().objects.create_user(
            email='other_img@rev.com', password='x',
        ))
        api_client.force_login(other)
        res = api_client.post(
            IMAGES_URL(prod_rev.id, pending_review.id),
            {'image': _make_png()},
            format='multipart',
        )
        assert res.status_code == 403
        assert res.json()['codigo_error'] == 'REVIEW_NOT_OWNER'

    def test_max_3_images_returns_400(self, auth_client, prod_rev, pending_review, db):
        """UC-REV-02 cap6: max 3 images per review enforced."""
        for _ in range(3):
            auth_client.post(
                IMAGES_URL(prod_rev.id, pending_review.id),
                {'image': _make_png()},
                format='multipart',
            )
        # 4th image must be rejected.
        res = auth_client.post(
            IMAGES_URL(prod_rev.id, pending_review.id),
            {'image': _make_png()},
            format='multipart',
        )
        assert res.status_code == 400
        assert res.json()['codigo_error'] == 'REVIEW_MAX_IMAGES_REACHED'

    def test_unauthenticated_returns_401(self, api_client, prod_rev, pending_review, db):
        """Unauthenticated request is rejected."""
        res = api_client.post(
            IMAGES_URL(prod_rev.id, pending_review.id),
            {'image': _make_png()},
            format='multipart',
        )
        assert res.status_code == 401


# =============================================================================
# PARTE 7B AC-02..AC-05 — manejo de error templado por UC (12 marcadores)
#
# Cobertura explicita de los 4 AC funcionales de error de UC-REV-01/02/03,
# agrupada por endpoint para evitar 12 tests triviales repetidos. Cada test
# lleva el id del marcador en su nombre (test_uc_rev_0X_...).
#
# DRIFT IMPORTANTE entre la plantilla del AC y la impl real (ver hallazgos
# en el reporte del agente):
#   - La plantilla AC-02 dice ``error_code = INVALID_PAYLOAD``; la impl NO
#     emite ese codigo. POST create usa el ValidationError default de DRF
#     (sin ``codigo_error``); POST reject usa ``REASON_INVALID``.
#   - La plantilla AC-04 dice ``error_code = NOT_FOUND``; la impl emite
#     codigos especificos: ``PRODUCT_NOT_FOUND``, ``ORDER_NOT_FOUND``,
#     ``REVIEW_NOT_FOUND``.
#   - La plantilla AC-03 (sin staff) dice 403; la impl usa el 403 default
#     de ``IsAdminUser`` SIN ``codigo_error=FORBIDDEN`` (PARTE 7.3 UC-REV-03).
# Los tests assertan lo que la impl REALMENTE emite (canon de codigo), y los
# nombres trazan al marcador del UC.
# =============================================================================

class TestUcRev01CreateErrorHandling:
    """UC-REV-01 — POST /api/v2/products/<pid>/reviews/ (crear resena)."""

    # --- AC-02: payload sin campos obligatorios -> 400, sin mutar estado ---
    def test_uc_rev_01_ac02_payload_invalido_400(
        self, auth_client, prod_rev, order_user_with_product, db,
    ):
        """AC-02: payload sin rating/title/body -> 400 validacion DRF.

        DRIFT: la plantilla pide ``INVALID_PAYLOAD``; la impl usa el
        ValidationError default de DRF (claves de campo faltante), sin
        ``codigo_error``. Se asserta 400 + que no se creo ninguna resena.
        """
        antes = Review.objects.count()
        r = auth_client.post(
            PRODUCT_REVIEWS_URL(prod_rev.id),
            {'order_id': order_user_with_product.id},  # faltan rating/title/body
            format='json',
        )
        assert r.status_code == 400
        body = r.json()
        # Campos obligatorios faltantes reportados por el serializer.
        assert any(k in body for k in ('rating', 'title', 'body')), body
        # POST-F01: no muta estado.
        assert Review.objects.count() == antes

    def test_uc_rev_01_ac02_rating_fuera_de_rango_400(
        self, auth_client, prod_rev, order_user_with_product, db,
    ):
        """AC-02 variante: rating fuera de 1..5 -> 400 sin mutar estado."""
        antes = Review.objects.count()
        r = auth_client.post(
            PRODUCT_REVIEWS_URL(prod_rev.id),
            {'order_id': order_user_with_product.id,
             'rating': 9, 'title': 'X', 'body': 'cuerpo de prueba'},
            format='json',
        )
        assert r.status_code == 400
        assert Review.objects.count() == antes

    # --- AC-03: sin credenciales (sin JWT) -> 401, no expone datos ---
    def test_uc_rev_01_ac03_sin_jwt_401(self, api_client, prod_rev, db):
        """AC-03: POST sin JWT -> 401 (IsAuthenticated). No expone recurso."""
        r = api_client.post(
            PRODUCT_REVIEWS_URL(prod_rev.id),
            {'order_id': 1, 'rating': 5, 'title': 'X', 'body': 'cuerpo'},
            format='json',
        )
        assert r.status_code == 401
        # RNF-SEC-003: no se filtran datos del producto/orden en el 401.
        assert 'results' not in r.json()

    # --- AC-04: recurso inexistente -> 404 codigo especifico ---
    def test_uc_rev_01_ac04_producto_inexistente_404(self, auth_client, db):
        """AC-04: product_id del path no existe -> 404 PRODUCT_NOT_FOUND.

        DRIFT: la plantilla pide ``NOT_FOUND``; la impl emite
        ``PRODUCT_NOT_FOUND`` (mas especifico).
        """
        r = auth_client.post(
            PRODUCT_REVIEWS_URL(999999),
            {'order_id': 1, 'rating': 5, 'title': 'X', 'body': 'cuerpo'},
            format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_FOUND'

    def test_uc_rev_01_ac04_orden_inexistente_404(self, auth_client, prod_rev, db):
        """AC-04 variante: order_id del body no existe -> 404 ORDER_NOT_FOUND."""
        r = auth_client.post(
            PRODUCT_REVIEWS_URL(prod_rev.id),
            {'order_id': 999999, 'rating': 5, 'title': 'X', 'body': 'cuerpo'},
            format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'ORDER_NOT_FOUND'

    # --- AC-05: excepcion documentada PARTE 5 -> codigo PARTE 7.3 ---
    def test_uc_rev_01_ac05_ex01_no_compro_403(self, auth_client, prod_rev, db):
        """AC-05 / EX-01: orden ajena (no compro) -> 403 PRODUCT_NOT_PURCHASED.

        PARTE 7.3 UC-REV-01: 403 codigo_error=PRODUCT_NOT_PURCHASED.
        """
        other = get_user_model().objects.create_user(
            email='ac05o@rev.com', password='x',
        )
        o = make_order(user=other, status='DELIVERED')
        r = auth_client.post(
            PRODUCT_REVIEWS_URL(prod_rev.id),
            {'order_id': o.id, 'rating': 4, 'title': 'X', 'body': 'cuerpo'},
            format='json',
        )
        assert r.status_code == 403
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_PURCHASED'

    def test_uc_rev_01_ac05_ex02_resena_duplicada_400(
        self, auth_client, user, prod_rev, order_user_with_product, db,
    ):
        """AC-05 / EX-02: resena duplicada -> codigo REVIEW_DUPLICATE.

        PARTE 7.3 documenta 409; la impl usa DRF ValidationError = 400 con
        codigo_error=REVIEW_DUPLICATE (drift menor de status, codigo OK).
        Estado consistente: sigue existiendo exactamente una resena.
        """
        Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='A', body='cuerpo original',
        )
        r = auth_client.post(
            PRODUCT_REVIEWS_URL(prod_rev.id),
            {'order_id': order_user_with_product.id,
             'rating': 3, 'title': 'C', 'body': 'otro cuerpo'},
            format='json',
        )
        assert r.status_code in (400, 409)
        assert r.json()['codigo_error'] == 'REVIEW_DUPLICATE'
        # Estado consistente: no se creo una segunda resena.
        assert Review.objects.filter(
            user=user, product=prod_rev,
        ).count() == 1


class TestUcRev02ViewErrorHandling:
    """UC-REV-02 — GET /api/v2/products/<pid>/reviews/ (ver resenas, publico)."""

    # AC-02 NO APLICA: GET no tiene payload obligatorio (sin body, solo path
    #   param + query opcional). Ver tabla del reporte: AC-02 marcado N/A.
    # AC-03 NO APLICA por permiso: el endpoint es AllowAny (publico). No exige
    #   JWT ni is_staff, asi que "sin credenciales" es el caso normal 200, no
    #   un error. Ver tabla del reporte: AC-03 marcado N/A.

    def test_uc_rev_02_ac03_publico_no_requiere_credenciales_200(
        self, api_client, prod_rev, db,
    ):
        """AC-03 (negativo intencional): GET es publico -> 200 sin JWT.

        Documenta que para UC-REV-02 el AC-03 no produce error: el actor sin
        credenciales es el caso esperado. RNF-SEC-003: solo expone APPROVED.
        """
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id))
        assert r.status_code == 200
        # Solo aprobadas: producto sin resenas aprobadas -> lista vacia.
        assert r.json()['results'] == []

    def test_uc_rev_02_ac04_producto_inexistente_404(self, api_client, db):
        """AC-04: product_id inexistente -> 404 PRODUCT_NOT_FOUND.

        DRIFT: plantilla pide NOT_FOUND; impl emite PRODUCT_NOT_FOUND.
        No filtra existencia cruzada (mismo codigo para cualquier id ausente).
        """
        r = api_client.get(PRODUCT_REVIEWS_URL(999999))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'PRODUCT_NOT_FOUND'

    # AC-05: EX-01 de UC-REV-02 es "Error del sistema" -> 500 SYSTEM_ERROR
    #   (PARTE 7.3). No es deterministicamente reproducible sin inyectar un
    #   fallo de infraestructura; queda fuera de cobertura de test de AC
    #   funcional (requeriria mock de la capa de datos). Ver hallazgo en el
    #   reporte. Se cubre el caso de filtro invalido como excepcion observable
    #   mas cercana documentada en la impl:
    def test_uc_rev_02_ac05_filtro_rating_invalido_400(self, api_client, prod_rev, db):
        """AC-05 (proxy observable): ?rating fuera de 1..5 -> 400 RATING_INVALID.

        La unica excepcion deterministica del GET en la impl. El EX-01
        (SYSTEM_ERROR 500) no es reproducible sin inyeccion de fallo.
        """
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'rating': '9'})
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'RATING_INVALID'


class TestUcRev03ModerateErrorHandling:
    """UC-REV-03 — admin moderar: GET cola, POST approve/reject (is_staff)."""

    @pytest.fixture
    def pending_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=3, title='Pend', body='cuerpo pendiente',
            status=Review.STATUS_PENDING,
        )

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product, sale_order=order_user_with_product.sale_order,
            rating=5, title='Aprov', body='cuerpo aprobado',
            status=Review.STATUS_APPROVED,
        )

    # --- AC-02: payload sin campos obligatorios -> 400 sin mutar estado ---
    def test_uc_rev_03_ac02_reject_sin_reason_400(
        self, admin_client, pending_review, db,
    ):
        """AC-02: POST reject sin ``reason`` obligatorio -> 400.

        DRIFT: plantilla pide INVALID_PAYLOAD; la impl emite REASON_INVALID.
        Estado consistente: la resena sigue PENDING (no se rechazo).
        """
        r = admin_client.patch(REJECT_URL(pending_review.id), {'action': 'reject'}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REASON_INVALID'
        pending_review.refresh_from_db()
        assert pending_review.status == Review.STATUS_PENDING

    def test_uc_rev_03_ac02_queue_status_invalido_400(self, admin_client, db):
        """AC-02 variante (query param invalido): ?status=X invalido -> 400."""
        r = admin_client.get(ADMIN_QUEUE_URL + '?status=NO_EXISTE')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'STATUS_INVALID'

    # --- AC-03: sin credenciales (sin JWT) -> 401; sin is_staff -> 403 ---
    def test_uc_rev_03_ac03_sin_jwt_401(self, api_client, db):
        """AC-03: GET cola admin sin JWT -> 401. No expone la cola."""
        r = api_client.get(ADMIN_QUEUE_URL)
        assert r.status_code == 401
        assert 'results' not in r.json()

    def test_uc_rev_03_ac03_sin_staff_403(
        self, auth_client, pending_review, db,
    ):
        """AC-03: usuario autenticado sin is_staff -> 403 (IsAdminUser).

        DRIFT PARTE 7.3 UC-REV-03: documenta codigo_error=FORBIDDEN, pero la
        impl usa el 403 default de DRF SIN codigo_error. Se asserta 403 y se
        documenta el drift en el reporte. RNF-SEC-003: no expone el recurso.
        """
        r = auth_client.patch(APPROVE_URL(pending_review.id), {'action': 'approve'}, format='json')
        assert r.status_code == 403
        # No se moderó: estado consistente.
        pending_review.refresh_from_db()
        assert pending_review.status == Review.STATUS_PENDING

    # --- AC-04: recurso inexistente -> 404 REVIEW_NOT_FOUND ---
    def test_uc_rev_03_ac04_approve_inexistente_404(self, admin_client, db):
        """AC-04: approve sobre pk inexistente -> 404 REVIEW_NOT_FOUND.

        DRIFT: plantilla pide NOT_FOUND; impl emite REVIEW_NOT_FOUND.
        """
        r = admin_client.patch(APPROVE_URL(999999), {'action': 'approve'}, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'REVIEW_NOT_FOUND'

    def test_uc_rev_03_ac04_reject_inexistente_404(self, admin_client, db):
        """AC-04 variante: reject sobre pk inexistente -> 404 REVIEW_NOT_FOUND."""
        r = admin_client.patch(
            REJECT_URL(999999), {'action': 'reject', 'reason': 'SPAM'}, format='json',
        )
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'REVIEW_NOT_FOUND'

    # --- AC-05: excepcion documentada PARTE 5 -> codigo PARTE 7.3 ---
    def test_uc_rev_03_ac05_ex02_ya_moderada_400(
        self, admin_client, approved_review, db,
    ):
        """AC-05 / EX-02: resena ya moderada por otro admin -> 400 consistente.

        PARTE 5 EX-02: "resena ya moderada por otro administrador". La impl
        materializa esto al intentar rechazar una resena ya APPROVED ->
        REVIEW_ALREADY_APPROVED. Estado consistente: sigue APPROVED.
        """
        r = admin_client.patch(
            REJECT_URL(approved_review.id), {'action': 'reject', 'reason': 'SPAM'}, format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_ALREADY_APPROVED'
        approved_review.refresh_from_db()
        assert approved_review.status == Review.STATUS_APPROVED
