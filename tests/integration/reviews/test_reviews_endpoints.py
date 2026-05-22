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
        ids = [row['id'] for row in r.json()]
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
