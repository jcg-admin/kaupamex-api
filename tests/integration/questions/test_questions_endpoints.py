"""
Tests — Product Questions endpoints (UC-QST-01..04)

Public:
  POST /api/v2/products/<id>/questions/                    public ask
  GET  /api/v2/products/<id>/questions/                    public list (approved only)

Admin:
  GET  /api/v2/admin/questions/?status=PENDING|ANSWERED|REJECTED
  POST /api/v2/admin/questions/<id>/answer/
  POST /api/v2/admin/questions/<id>/approve/
  POST /api/v2/admin/questions/<id>/reject/

JSON keys + identifiers in English (DEC-DOC-005).
"""
from decimal import Decimal
from apps.catalogue.models import Category, Product
from apps.questions.models import ProductQuestion

import pytest

pytestmark = pytest.mark.integration


# ─── fixtures locales ────────────────────────────────────────────────────
@pytest.fixture
def category(db):
    return Category.objects.create(
        name='Catq', slug='catq', is_active=True,
    )


@pytest.fixture
def product(db, category):
    _p = Product.objects.create(
        name='Prodq', slug='prodq', sku='Q-001',
        description='',
        price=Decimal('100.00'), stock=10,
        is_active=True, is_published=True,
    )
    _p.categories.add(category)
    return _p


def _q_url(product_id):
    return f'/api/v2/products/{product_id}/questions/'


def _admin_list_url(suffix=''):
    return f'/api/v2/admin/questions/{suffix}'


def _make_question(product, **kwargs):
    defaults = {
        'product': product,
        'body': 'Una pregunta de prueba',
        'asker_name': 'Anon',
        'asker_email': 'a@example.com',
        'status': 'PENDING',
    }
    defaults.update(kwargs)
    return ProductQuestion.objects.create(**defaults)


# ─── POST /products/<id>/questions — public ask ──────────────────────────
class TestPublicAsk:
    def test_anonymous_can_ask_with_name_and_email(self, api_client, product, db):
        res = api_client.post(_q_url(product.pk), {
            'body': 'Tienen este producto en verde?',
            'asker_name': 'Carla',
            'asker_email': 'carla@example.com',
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        assert body['product'] == product.pk
        assert body['status'] == 'PENDING'

        q = ProductQuestion.objects.get(pk=body['id'])
        assert q.asker_name == 'Carla'
        assert q.asker_email == 'carla@example.com'
        assert q.asker_user is None

    def test_authenticated_can_ask_without_name(self, auth_client, product, db):
        res = auth_client.post(_q_url(product.pk), {
            'body': 'Cuanto pesa?',
        }, format='json')
        assert res.status_code == 201

        q = ProductQuestion.objects.get(pk=res.json()['id'])
        assert q.asker_user_id is not None

    def test_anonymous_without_name_returns_400(self, api_client, product, db):
        res = api_client.post(_q_url(product.pk), {
            'body': 'Pregunta sin datos',
            'asker_email': 'x@example.com',
        }, format='json')
        assert res.status_code == 400

    def test_anonymous_without_email_returns_400(self, api_client, product, db):
        res = api_client.post(_q_url(product.pk), {
            'body': 'Pregunta sin email',
            'asker_name': 'Anon',
        }, format='json')
        assert res.status_code == 400

    def test_404_for_unknown_product(self, api_client, db):
        res = api_client.post(_q_url(999999), {
            'body': 'X',
            'asker_name': 'Anon',
            'asker_email': 'a@example.com',
        }, format='json')
        assert res.status_code == 404

    def test_short_body_rejected(self, api_client, product, db):
        res = api_client.post(_q_url(product.pk), {
            'body': 'X',
            'asker_name': 'Anon',
            'asker_email': 'a@example.com',
        }, format='json')
        assert res.status_code == 400


# ─── GET /products/<id>/questions — public list ──────────────────────────
class TestPublicList:
    def test_list_only_answered_visible(self, api_client, product, db):
        _make_question(product, status='PENDING', body='Pendiente')
        _make_question(product, status='REJECTED', body='Rechazada')
        _make_question(
            product, status='ANSWERED', body='Visible',
            answer_body='Hola, si.',
        )
        res = api_client.get(_q_url(product.pk))
        assert res.status_code == 200
        rows = res.json()['results']
        assert len(rows) == 1
        assert rows[0]['body'] == 'Visible'
        assert rows[0]['answer_body'] == 'Hola, si.'

    def test_list_returns_empty_when_none(self, api_client, product, db):
        res = api_client.get(_q_url(product.pk))
        assert res.status_code == 200
        assert res.json()['results'] == []

    def test_list_404_for_unknown_product(self, api_client, db):
        res = api_client.get(_q_url(999999))
        assert res.status_code == 404

    def test_answered_without_answer_body_not_visible(self, api_client, product, db):
        _make_question(product, status='ANSWERED', body='Q1', answer_body='')
        res = api_client.get(_q_url(product.pk))
        assert res.status_code == 200
        assert res.json()['results'] == []


# ─── GET /admin/questions — admin queue ──────────────────────────────────
class TestAdminQueue:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(_admin_list_url())
        assert res.status_code == 401

    def test_requires_staff(self, auth_client, db):
        res = auth_client.get(_admin_list_url())
        assert res.status_code == 403

    def test_admin_lists_all(self, admin_client, product, db):
        _make_question(product, status='PENDING')
        _make_question(product, status='ANSWERED', answer_body='X')
        _make_question(product, status='REJECTED')
        res = admin_client.get(_admin_list_url())
        assert res.status_code == 200
        assert len(res.json()['results']) == 3

    def test_admin_filter_by_status(self, admin_client, product, db):
        _make_question(product, status='PENDING')
        _make_question(product, status='ANSWERED', answer_body='Y')
        res = admin_client.get(_admin_list_url('?status=PENDING'))
        assert res.status_code == 200
        rows = res.json()['results']
        assert len(rows) == 1
        assert rows[0]['status'] == 'PENDING'

    def test_admin_invalid_status_returns_400(self, admin_client, db):
        res = admin_client.get(_admin_list_url('?status=BOGUS'))
        assert res.status_code == 400


# ─── POST /admin/questions/<id>/answer ───────────────────────────────────
class TestAdminAnswer:
    def test_requires_staff(self, auth_client, product, db):
        q = _make_question(product)
        res = auth_client.post(_admin_list_url(f'{q.pk}/answer/'),
                               {'answer_body': 'Hola'}, format='json')
        assert res.status_code == 403

    def test_admin_answers_question(self, admin_client, product, db):
        q = _make_question(product, status='PENDING')
        res = admin_client.post(_admin_list_url(f'{q.pk}/answer/'),
                                {'answer_body': 'Si, hay verde.'},
                                format='json')
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == 'ANSWERED'
        assert body['answer_body'] == 'Si, hay verde.'

        q.refresh_from_db()
        assert q.answered_at is not None
        assert q.answered_by_id is not None

    def test_answer_body_required(self, admin_client, product, db):
        q = _make_question(product)
        res = admin_client.post(_admin_list_url(f'{q.pk}/answer/'),
                                {}, format='json')
        assert res.status_code == 400


# ─── POST /admin/questions/<id>/approve ──────────────────────────────────
class TestAdminApprove:
    def test_requires_staff(self, auth_client, product, db):
        q = _make_question(product)
        res = auth_client.post(_admin_list_url(f'{q.pk}/approve/'))
        assert res.status_code == 403

    def test_approve_without_answer_returns_409(self, admin_client, product, db):
        q = _make_question(product, status='PENDING', answer_body='')
        res = admin_client.post(_admin_list_url(f'{q.pk}/approve/'))
        assert res.status_code == 409

    def test_approve_answered_question(self, admin_client, product, db):
        q = _make_question(
            product, status='PENDING', answer_body='Respuesta lista.',
        )
        res = admin_client.post(_admin_list_url(f'{q.pk}/approve/'))
        assert res.status_code == 200
        assert res.json()['status'] == 'ANSWERED'


# ─── POST /admin/questions/<id>/reject ───────────────────────────────────
class TestAdminReject:
    def test_requires_staff(self, auth_client, product, db):
        q = _make_question(product)
        res = auth_client.post(_admin_list_url(f'{q.pk}/reject/'))
        assert res.status_code == 403

    def test_admin_rejects_question(self, admin_client, product, db):
        q = _make_question(product, status='PENDING')
        res = admin_client.post(_admin_list_url(f'{q.pk}/reject/'))
        assert res.status_code == 200
        assert res.json()['status'] == 'REJECTED'
        q.refresh_from_db()
        assert q.status == 'REJECTED'
