"""
Tests — Customer Card Management (Checkout API v2)

Covers:
  POST   /api/v2/payments/cards/              save card + email verification
  GET    /api/v2/payments/cards/              list active cards
  GET    /api/v2/payments/cards/{id}/         card detail
  PUT    /api/v2/payments/cards/{id}/         update card
  DELETE /api/v2/payments/cards/{id}/         delete card
  GET    /api/v2/payments/cards/verify/{tok}/ activate card via email link
"""
import pytest
from unittest.mock import patch, MagicMock

from apps.payments.models import SavedCard
from apps.settings_app.models import PaymentGateway

pytestmark = pytest.mark.integration

CARDS_URL   = '/api/v2/payments/cards/'
VERIFY_BASE = '/api/v2/payments/cards/verify/'


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mp_gw_cards(db, admin_user):
    gw = PaymentGateway(
        name='MP Cards Test',
        gateway='MERCADOPAGO',
        is_active=True,
    )
    gw.set_credentials({
        'access_token': 'TEST-ACCESS-CARDS-FAKE',
        'public_key':   'TEST-PK-CARDS-FAKE',
    })
    gw.save()
    return gw


MP_CARD_RESPONSE = {
    'id': 'CARD-ID-001',
    'expiration_month': 12,
    'expiration_year': 2028,
    'first_six_digits': '503143',
    'last_four_digits': '6351',
    'payment_method': {
        'id': 'master',
        'name': 'master',
        'payment_type_id': 'credit_card',
        'thumbnail': 'http://img.example.com/master.gif',
        'secure_thumbnail': 'https://img.example.com/master.gif',
    },
    'security_code': {'length': 3, 'card_location': 'back'},
    'issuer': {'id': 24, 'name': 'master'},
    'cardholder': {'name': 'APRO', 'identification': {'number': '19119119100', 'type': 'CURP'}},
    'date_created': '2026-06-27T10:00:00.000-06:00',
    'date_last_updated': '2026-06-27T10:00:00.000-06:00',
    'customer_id': 'CUST-001',
    'user_id': '12345',
    'live_mode': False,
}


@pytest.fixture
def active_saved_card(db, user):
    return SavedCard.objects.create(
        user=user,
        mp_card_id='CARD-ID-ACTIVE',
        mp_customer_id='CUST-001',
        last_four_digits='1234',
        first_six_digits='411111',
        expiration_month=6,
        expiration_year=2027,
        payment_method_id='visa',
        cardholder_name='Test User',
        status=SavedCard.STATUS_ACTIVE,
    )


@pytest.fixture
def pending_saved_card(db, user):
    return SavedCard.objects.create(
        user=user,
        mp_card_id='CARD-ID-PENDING',
        mp_customer_id='CUST-001',
        last_four_digits='9999',
        first_six_digits='503143',
        expiration_month=12,
        expiration_year=2028,
        payment_method_id='master',
        cardholder_name='APRO',
        status=SavedCard.STATUS_PENDING,
    )


# =============================================================================
# POST /cards/ — Save card + email verification
# =============================================================================

@pytest.mark.django_db
def test_save_card_creates_pending_and_sends_email(auth_client, user, mp_gw_cards):
    user.mp_customer_id = 'CUST-001'
    user.save(update_fields=['mp_customer_id'])

    mp_mock = MagicMock()
    mp_mock.card.return_value.create.return_value = {
        'status': 201,
        'response': MP_CARD_RESPONSE,
    }

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock), \
         patch('apps.payments.views.send_card_verification_email') as mock_email:
        resp = auth_client.post(CARDS_URL, {
            'token': 'TEST-CARD-TOKEN-ABCDEF',
        }, content_type='application/json')

    assert resp.status_code == 201, resp.data
    assert resp.data['status'] == SavedCard.STATUS_PENDING
    assert resp.data['verification_sent'] is True

    saved = SavedCard.objects.get(mp_card_id='CARD-ID-001', user=user)
    assert saved.status == SavedCard.STATUS_PENDING
    assert saved.last_four_digits == '6351'
    assert saved.payment_method_id == 'master'

    mock_email.assert_called_once()
    call_kwargs = mock_email.call_args
    assert call_kwargs[1]['last_four'] == '6351' or call_kwargs[0][3] == '6351'


@pytest.mark.django_db
def test_save_card_no_customer_id_auto_creates(auth_client, user, mp_gw_cards):
    """Si el usuario no tiene mp_customer_id, debe crearlo antes de guardar."""
    assert not user.mp_customer_id

    mp_mock = MagicMock()
    mp_mock.customer.return_value.search.return_value = {
        'status': 200,
        'response': {'results': []},
    }
    mp_mock.customer.return_value.create.return_value = {
        'status': 201,
        'response': {'id': 'CUST-NUEVO-001'},
    }
    mp_mock.card.return_value.create.return_value = {
        'status': 201,
        'response': MP_CARD_RESPONSE,
    }

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock), \
         patch('apps.payments.views.send_card_verification_email'):
        resp = auth_client.post(CARDS_URL, {
            'token': 'TEST-TOKEN-NUEVO',
        }, content_type='application/json')

    assert resp.status_code == 201, resp.data


@pytest.mark.django_db
def test_save_card_requires_token(auth_client, user, mp_gw_cards):
    resp = auth_client.post(CARDS_URL, {}, content_type='application/json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_save_card_duplicate_returns_200(auth_client, user, active_saved_card, mp_gw_cards):
    """Guardar la misma tarjeta dos veces devuelve 200 (idempotente)."""
    user.mp_customer_id = 'CUST-001'
    user.save(update_fields=['mp_customer_id'])

    duplicate_mp_response = dict(MP_CARD_RESPONSE)
    duplicate_mp_response['id'] = 'CARD-ID-ACTIVE'
    duplicate_mp_response['last_four_digits'] = '1234'

    mp_mock = MagicMock()
    mp_mock.card.return_value.create.return_value = {
        'status': 201,
        'response': duplicate_mp_response,
    }

    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock), \
         patch('apps.payments.views.send_card_verification_email') as mock_email:
        resp = auth_client.post(CARDS_URL, {
            'token': 'TEST-DUP-TOKEN',
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data
    assert resp.data['verification_sent'] is False
    mock_email.assert_not_called()


# =============================================================================
# GET /cards/ — List active cards
# =============================================================================

@pytest.mark.django_db
def test_list_cards_only_returns_active(auth_client, user, active_saved_card, pending_saved_card):
    resp = auth_client.get(CARDS_URL)
    assert resp.status_code == 200
    ids = [c['id'] for c in resp.data]
    assert active_saved_card.mp_card_id in ids
    assert pending_saved_card.mp_card_id not in ids


@pytest.mark.django_db
def test_list_cards_unauthenticated_returns_401(client):
    resp = client.get(CARDS_URL)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_list_cards_empty_for_new_user(auth_client, user):
    resp = auth_client.get(CARDS_URL)
    assert resp.status_code == 200
    assert resp.data == []


# =============================================================================
# GET /cards/{id}/ — Card detail
# =============================================================================

@pytest.mark.django_db
def test_get_card_detail_active(auth_client, active_saved_card):
    url = f'{CARDS_URL}{active_saved_card.mp_card_id}/'
    resp = auth_client.get(url)
    assert resp.status_code == 200
    assert resp.data['id'] == active_saved_card.mp_card_id
    assert resp.data['last_four_digits'] == active_saved_card.last_four_digits


@pytest.mark.django_db
def test_get_card_detail_not_found(auth_client, user):
    resp = auth_client.get(f'{CARDS_URL}NONEXISTENT-CARD/')
    assert resp.status_code == 404


@pytest.mark.django_db
def test_get_deleted_card_returns_404(auth_client, user):
    deleted = SavedCard.objects.create(
        user=user,
        mp_card_id='CARD-DELETED-001',
        mp_customer_id='CUST-001',
        last_four_digits='0000',
        first_six_digits='123456',
        expiration_month=1,
        expiration_year=2025,
        payment_method_id='visa',
        status=SavedCard.STATUS_DELETED,
    )
    resp = auth_client.get(f'{CARDS_URL}{deleted.mp_card_id}/')
    assert resp.status_code == 404


# =============================================================================
# PUT /cards/{id}/ — Update card
# =============================================================================

@pytest.mark.django_db
def test_update_card_expiration(auth_client, user, active_saved_card, mp_gw_cards):
    mp_mock = MagicMock()
    mp_mock.card.return_value.update.return_value = {
        'status': 200,
        'response': dict(MP_CARD_RESPONSE, expiration_year=2030),
    }

    url = f'{CARDS_URL}{active_saved_card.mp_card_id}/'
    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.put(url, {
            'expiration_year': 2030,
        }, content_type='application/json')

    assert resp.status_code == 200, resp.data
    assert resp.data['expiration_year'] == 2030
    active_saved_card.refresh_from_db()
    assert active_saved_card.expiration_year == 2030


@pytest.mark.django_db
def test_update_card_cardholder_name(auth_client, user, active_saved_card, mp_gw_cards):
    mp_mock = MagicMock()
    mp_mock.card.return_value.update.return_value = {
        'status': 200,
        'response': dict(MP_CARD_RESPONSE, cardholder={'name': 'NUEVO TITULAR'}),
    }

    url = f'{CARDS_URL}{active_saved_card.mp_card_id}/'
    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.put(url, {
            'cardholder_name': 'NUEVO TITULAR',
        }, content_type='application/json')

    assert resp.status_code == 200
    active_saved_card.refresh_from_db()
    assert active_saved_card.cardholder_name == 'NUEVO TITULAR'


@pytest.mark.django_db
def test_update_card_empty_body_returns_400(auth_client, active_saved_card):
    url = f'{CARDS_URL}{active_saved_card.mp_card_id}/'
    resp = auth_client.put(url, {}, content_type='application/json')
    assert resp.status_code == 400


# =============================================================================
# DELETE /cards/{id}/ — Delete card
# =============================================================================

@pytest.mark.django_db
def test_delete_card_marks_as_deleted(auth_client, user, active_saved_card, mp_gw_cards):
    mp_mock = MagicMock()
    mp_mock.card.return_value.delete.return_value = {
        'status': 200,
        'response': MP_CARD_RESPONSE,
    }

    url = f'{CARDS_URL}{active_saved_card.mp_card_id}/'
    with patch('apps.payments.gateways.mercadopago._get_sdk', return_value=mp_mock):
        resp = auth_client.delete(url)

    assert resp.status_code == 204
    active_saved_card.refresh_from_db()
    assert active_saved_card.status == SavedCard.STATUS_DELETED


@pytest.mark.django_db
def test_delete_nonexistent_card_returns_404(auth_client, user):
    resp = auth_client.delete(f'{CARDS_URL}NONEXISTENT/')
    assert resp.status_code == 404


# =============================================================================
# GET /cards/verify/{token}/ — Email verification link
# =============================================================================

@pytest.mark.django_db
def test_verify_token_activates_card(client, pending_saved_card):
    url = f'{VERIFY_BASE}{pending_saved_card.verification_token}/'
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp.data['status'] == SavedCard.STATUS_ACTIVE
    pending_saved_card.refresh_from_db()
    assert pending_saved_card.status == SavedCard.STATUS_ACTIVE


@pytest.mark.django_db
def test_verify_token_already_active_is_idempotent(client, active_saved_card):
    url = f'{VERIFY_BASE}{active_saved_card.verification_token}/'
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data['status'] == SavedCard.STATUS_ACTIVE


@pytest.mark.django_db
def test_verify_invalid_token_returns_404(client):
    resp = client.get(f'{VERIFY_BASE}invalid-token-xyz/')
    assert resp.status_code == 404


@pytest.mark.django_db
def test_verify_deleted_card_returns_410(client, user):
    deleted = SavedCard.objects.create(
        user=user,
        mp_card_id='CARD-DEL-VER',
        mp_customer_id='CUST-001',
        last_four_digits='7777',
        first_six_digits='411111',
        expiration_month=3,
        expiration_year=2025,
        payment_method_id='visa',
        status=SavedCard.STATUS_DELETED,
    )
    resp = client.get(f'{VERIFY_BASE}{deleted.verification_token}/')
    assert resp.status_code == 410


@pytest.mark.django_db
def test_verify_no_auth_required(client, pending_saved_card):
    """El enlace del email es público — no requiere login."""
    url = f'{VERIFY_BASE}{pending_saved_card.verification_token}/'
    resp = client.get(url)
    assert resp.status_code == 200
