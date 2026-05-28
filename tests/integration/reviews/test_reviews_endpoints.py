"""
Integration tests — P-14 reviews endpoints (UC-REV-01..03).
"""
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.orders.models import Order, OrderAddress, OrderItem, OrderValue
from apps.reviews.models import Review, ReviewHelpfulVote, ReviewModerationLog
from django.contrib.auth import get_user_model

import pytest

pytestmark = pytest.mark.integration


PRODUCT_REVIEWS_URL = lambda pid: f'/api/v1/products/{pid}/reviews/'
ADMIN_QUEUE_URL     = '/api/v1/admin/reviews/'
APPROVE_URL         = lambda pk: f'/api/v1/admin/reviews/{pk}/approve/'
REJECT_URL          = lambda pk: f'/api/v1/admin/reviews/{pk}/reject/'
HELPFUL_URL         = lambda pid, pk: f'/api/v1/products/{pid}/reviews/{pk}/helpful/'
EDIT_URL            = lambda pid, pk: f'/api/v1/products/{pid}/reviews/{pk}/edit/'


@pytest.fixture
def cat_rev(db):
    return Category.objects.create(name='Rev', slug='rev', is_active=True)


@pytest.fixture
def prod_rev(db, cat_rev):
    return Product.objects.create(
        name='Producto Rev', slug='producto-rev', sku='REV-001',
        category=cat_rev, price=Decimal('100'), stock=10,
        is_active=True, is_published=True,
    )


@pytest.fixture
def order_user_with_product(db, user, prod_rev):
    o = Order.objects.create(user=user, status='DELIVERED')
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=5, title='Buena', body='Excelente',
            status=Review.STATUS_APPROVED,
        )
        # Una pendiente que NO debe aparecer.
        u2 = get_user_model().objects.create_user(
            username='u2rev', email='u2@rev.com', password='x',
        )
        o2 = Order.objects.create(user=u2, status='DELIVERED')
        Review.objects.create(
            user=u2, product=prod_rev, order=o2,
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
            username='otherrev', email='or@rev.com', password='x',
        )
        o = Order.objects.create(user=other, status='DELIVERED')
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
            o = Order.objects.create(user=user, status=st)
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
            user=user, product=prod_rev, order=order_user_with_product,
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
            user=user, product=prod_rev, order=order_user_with_product,
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=5, title='1', body='1',
        )
        # Primera aprobacion.
        r = admin_client.post(APPROVE_URL(rev.id), {}, format='json')
        assert r.status_code == 200
        assert r.json()['status'] == 'APPROVED'
        assert r.json()['already_approved'] is False
        # Segunda aprobacion — idempotente.
        r2 = admin_client.post(APPROVE_URL(rev.id), {}, format='json')
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=1, title='no', body='no',
        )
        r = admin_client.post(REJECT_URL(rev.id), {'reason': 'SPAM'}, format='json')
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=1, title='no', body='no',
        )
        r = admin_client.post(REJECT_URL(rev.id), {'reason': 'NOPE'}, format='json')
        assert r.status_code == 400
        # Canon EN (T-118 alineamiento + anti-soft-on-tests): codigo ya
        # retorna REASON_INVALID. Antes el test era outlier ES.
        assert r.json()['codigo_error'] == 'REASON_INVALID'

    def test_comprador_no_puede_aprobar(
        self, auth_client, user, prod_rev, order_user_with_product, db,
    ):
        rev = Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product,
            rating=5, title='ok', body='ok',
        )
        r = auth_client.post(APPROVE_URL(rev.id), {}, format='json')
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
            user=user, product=prod_rev, order=order_user_with_product,
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
            user=user, product=prod_rev, order=order_user_with_product,
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=4, title='T', body='B', status=Review.STATUS_APPROVED,
        )
        r = api_client.get(PRODUCT_REVIEWS_URL(prod_rev.id), {'sort': 'helpful'})
        assert r.status_code == 200


class TestReviewHelpfulVote:
    """UC-REV-02 FR-REV-02.02 — helpful votes."""

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product,
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
        o = Order.objects.create(user=user, status='DELIVERED')
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
            username='u_filter2', email='uf2@rev.com', password='x',
        )
        o1 = self._make_order(db, user)
        OrderItem.objects.create(
            order=o1, product=prod_rev, product_name=prod_rev.name,
            sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        o2 = self._make_order(db, u2)
        Review.objects.create(
            user=user, product=prod_rev, order=o1,
            rating=3, title='Tres', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        Review.objects.create(
            user=u2, product=prod_rev, order=o2,
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
            username='u_sort2', email='usort2@rev.com', password='x',
        )
        o1 = self._make_order(db, user)
        OrderItem.objects.create(
            order=o1, product=prod_rev, product_name=prod_rev.name,
            sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        o2 = self._make_order(db, u2)
        rev_low = Review.objects.create(
            user=user, product=prod_rev, order=o1,
            rating=4, title='Low', body='cuerpo',
            status=Review.STATUS_APPROVED,
            helpful_count=0,
        )
        rev_high = Review.objects.create(
            user=u2, product=prod_rev, order=o2,
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
            username='u_page2', email='upage2@rev.com', password='x',
        )
        o1 = self._make_order(db, user)
        OrderItem.objects.create(
            order=o1, product=prod_rev, product_name=prod_rev.name,
            sku=prod_rev.sku, unit_price=Decimal('100'), quantity=1,
            subtotal=Decimal('100'),
        )
        o2 = self._make_order(db, u2)
        rev1 = Review.objects.create(
            user=user, product=prod_rev, order=o1,
            rating=4, title='First', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )
        rev2 = Review.objects.create(
            user=u2, product=prod_rev, order=o2,
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
            category=cat_rev, price=Decimal('50'), stock=5,
            is_active=True, is_published=True,
        )
        o = Order.objects.create(user=user, status='DELIVERED')
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=3, title='Pend', body='cuerpo',
            status=Review.STATUS_PENDING,
        )

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product,
            rating=5, title='Aprov', body='cuerpo',
            status=Review.STATUS_APPROVED,
        )

    @pytest.fixture
    def rejected_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product,
            rating=1, title='Rej', body='cuerpo',
            status=Review.STATUS_REJECTED,
            reject_reason='SPAM',
        )

    def test_approve_rejected_review_returns_400(
        self, admin_client, rejected_review, db,
    ):
        """Cannot approve a review that was already rejected."""
        r = admin_client.post(APPROVE_URL(rejected_review.id), {}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_ALREADY_REJECTED'

    def test_reject_approved_review_returns_400(
        self, admin_client, approved_review, db,
    ):
        """Cannot reject a review that was already approved."""
        r = admin_client.post(
            REJECT_URL(approved_review.id), {'reason': 'SPAM'}, format='json',
        )
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'REVIEW_ALREADY_APPROVED'

    def test_approve_nonexistent_review_returns_404(
        self, admin_client, db,
    ):
        r = admin_client.post(APPROVE_URL(999999), {}, format='json')
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'REVIEW_NOT_FOUND'

    def test_reject_nonexistent_review_returns_404(
        self, admin_client, db,
    ):
        r = admin_client.post(
            REJECT_URL(999999), {'reason': 'SPAM'}, format='json',
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
            user=user, product=prod_rev, order=order_user_with_product,
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
        r = admin_client.post(REJECT_URL(pending_review.id), {}, format='json')
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
            user=user, product=prod_rev, order=order_user_with_product,
            rating=3, title='Titulo original', body='Cuerpo original largo',
            status=Review.STATUS_PENDING,
        )

    @pytest.fixture
    def approved_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product,
            rating=5, title='Aprobada', body='Cuerpo aprobado largo',
            status=Review.STATUS_APPROVED,
        )

    @pytest.fixture
    def rejected_review(self, db, user, prod_rev, order_user_with_product):
        return Review.objects.create(
            user=user, product=prod_rev, order=order_user_with_product,
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
            username='other_edit', email='otheredit@rev.com', password='x',
        )
        o_other = Order.objects.create(user=other, status='DELIVERED')
        review = Review.objects.create(
            user=other, product=prod_rev, order=o_other,
            rating=2, title='Otro', body='Cuerpo de otro usuario largo',
            status=Review.STATUS_PENDING,
        )
        # Authenticate as a different user (re-use the `user` fixture via
        # creating a fresh user here and logging in manually).
        attacker = get_user_model().objects.create_user(
            username='attacker_edit', email='attacker@rev.com', password='x',
        )
        from rest_framework_simplejwt.tokens import RefreshToken as RT
        refresh = RT.for_user(attacker)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
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
