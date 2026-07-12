"""
Tests — Notifications endpoints (UC-NOT-01..07)

Reads:
  GET   /api/v2/notifications/                      list
  GET   /api/v2/notifications/unread-count/         unread count
  GET   /api/v2/notifications/preferences/          list preferences
  GET   /api/v2/admin/notifications/audience-count/ audience size

Mutations:
  PATCH /api/v2/notifications/<pk>/             mark one as read
  PATCH /api/v2/notifications/                  mark all as read
  PUT   /api/v2/notifications/preferences/      update preferences
  POST  /api/v2/admin/notifications/            send manual

JSON keys + identifiers in English (DEC-DOC-005).
"""
import pytest
from apps.notifications.models import Notification, NotificationPreference

pytestmark = pytest.mark.integration

LIST_URL = '/api/v2/notifications/'
UNREAD_COUNT_URL = '/api/v2/notifications/unread-count/'
PREFERENCES_URL = '/api/v2/notifications/preferences/'
ADMIN_AUDIENCE_URL = '/api/v2/admin/notifications/audience-count/'
ADMIN_MANUAL_URL = '/api/v2/admin/notifications/'


# ─── helpers ─────────────────────────────────────────────────────────────
def _make_notification(user, **kwargs):
    defaults = {
        'user': user,
        'type': 'SYSTEM',
        'subject': 'Asunto',
        'body': 'Cuerpo del mensaje',
        'read': False,
    }
    defaults.update(kwargs)
    return Notification.objects.create(**defaults)


# ─── GET / list ──────────────────────────────────────────────────────────
class TestListNotifications:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(LIST_URL)
        assert res.status_code == 401

    def test_list_only_own_notifications(self, auth_client, user, admin_user, db):
        _make_notification(user, subject='Mio')
        _make_notification(admin_user, subject='De otro')
        res = auth_client.get(LIST_URL)
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        assert len(body['results']) == 1
        item = body['results'][0]
        assert item['subject'] == 'Mio'
        for key in ('id', 'type', 'subject', 'body', 'is_read', 'created_at'):
            assert key in item

    def test_returns_empty_results_when_none(self, auth_client, db):
        res = auth_client.get(LIST_URL)
        assert res.status_code == 200
        assert res.json()['results'] == []


# ─── GET /unread-count ───────────────────────────────────────────────────
class TestUnreadCount:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(UNREAD_COUNT_URL)
        assert res.status_code == 401

    def test_counts_only_unread_for_user(self, auth_client, user, admin_user, db):
        _make_notification(user, subject='A', read=False)
        _make_notification(user, subject='B', read=False)
        _make_notification(user, subject='C', read=True)
        _make_notification(admin_user, subject='D', read=False)
        res = auth_client.get(UNREAD_COUNT_URL)
        assert res.status_code == 200
        assert res.json() == {'count': 2}


# ─── POST /{id}/read ─────────────────────────────────────────────────────
class TestMarkRead:
    def test_requires_auth(self, api_client, user, db):
        notif = _make_notification(user)
        res = api_client.patch(f'{LIST_URL}{notif.pk}/')
        assert res.status_code == 401

    def test_marks_own_notification_as_read(self, auth_client, user, db):
        notif = _make_notification(user, read=False)
        res = auth_client.patch(f'{LIST_URL}{notif.pk}/')
        assert res.status_code == 200
        notif.refresh_from_db()
        assert notif.read is True

    def test_returns_404_for_other_user(self, auth_client, admin_user, db):
        notif = _make_notification(admin_user)
        res = auth_client.patch(f'{LIST_URL}{notif.pk}/')
        assert res.status_code == 404

    def test_returns_404_for_missing(self, auth_client, db):
        res = auth_client.patch(f'{LIST_URL}999999/')
        assert res.status_code == 404


# ─── PATCH / (mark all read) ─────────────────────────────────────────────
class TestMarkAllRead:
    def test_requires_auth(self, api_client, db):
        res = api_client.patch(LIST_URL)
        assert res.status_code == 401

    def test_marks_all_user_notifications_as_read(self, auth_client, user, admin_user, db):
        _make_notification(user, read=False)
        _make_notification(user, read=False)
        other = _make_notification(admin_user, read=False)
        res = auth_client.patch(LIST_URL)
        assert res.status_code == 200
        assert res.json()['updated'] == 2

        assert Notification.objects.filter(user=user, read=False).count() == 0
        # ajeno permanece sin tocar
        other.refresh_from_db()
        assert other.read is False


# ─── GET /preferences ────────────────────────────────────────────────────
class TestGetPreferences:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(PREFERENCES_URL)
        assert res.status_code == 401

    def test_returns_all_types_with_mandatory_flag(self, auth_client, db):
        res = auth_client.get(PREFERENCES_URL)
        assert res.status_code == 200
        body = res.json()
        assert 'results' in body
        rows = body['results']
        types = {r['type'] for r in rows}
        # tipos esperados
        assert {'ORDER_UPDATE', 'RETURN_UPDATE', 'PROMOTION', 'SYSTEM'} <= types
        for row in rows:
            for key in ('type', 'enabled', 'mandatory', 'label'):
                assert key in row
        by_type = {r['type']: r for r in rows}
        assert by_type['ORDER_UPDATE']['mandatory'] is True
        assert by_type['ORDER_UPDATE']['enabled'] is True
        assert by_type['PROMOTION']['mandatory'] is False
        # default es enabled=True para opcionales sin fila
        assert by_type['PROMOTION']['enabled'] is True


# ─── PUT /preferences ────────────────────────────────────────────────────
class TestUpdatePreferences:
    def test_requires_auth(self, api_client, db):
        res = api_client.put(PREFERENCES_URL,
                             {'preferences': [{'type': 'PROMOTION', 'enabled': False}]},
                             format='json')
        assert res.status_code == 401

    def test_disables_optional_preference(self, auth_client, user, db):
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'PROMOTION', 'enabled': False}],
        }, format='json')
        assert res.status_code == 200
        body = res.json()
        by_type = {r['type']: r for r in body['results']}
        assert by_type['PROMOTION']['enabled'] is False

        pref = NotificationPreference.objects.get(user=user, type='PROMOTION')
        assert pref.enabled is False

    def test_mandatory_type_cannot_be_disabled(self, auth_client, db):
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'ORDER_UPDATE', 'enabled': False}],
        }, format='json')
        assert res.status_code == 200
        body = res.json()
        by_type = {r['type']: r for r in body['results']}
        assert by_type['ORDER_UPDATE']['enabled'] is True
        assert by_type['ORDER_UPDATE']['mandatory'] is True
        assert body.get('skipped_mandatory') == ['ORDER_UPDATE']

    def test_skipped_mandatory_empty_when_only_optional(self, auth_client, db):
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'PROMOTION', 'enabled': False}],
        }, format='json')
        assert res.status_code == 200
        assert res.json().get('skipped_mandatory') == []

    def test_skipped_mandatory_only_when_disabling(self, auth_client, db):
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'SYSTEM', 'enabled': True}],
        }, format='json')
        assert res.status_code == 200
        assert res.json().get('skipped_mandatory') == []

    def test_invalid_type_returns_400(self, auth_client, db):
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'BOGUS', 'enabled': False}],
        }, format='json')
        assert res.status_code == 400

    def test_disable_promotion_and_support_together(self, auth_client, user, db):
        """H-NOT-01: deshabilitar Promociones + Actualizaciones de soporte a la
        vez debe devolver 200 (era el flujo que reportaba 500 en prod)."""
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [
                {'type': 'PROMOTION', 'enabled': False},
                {'type': 'SUPPORT_UPDATE', 'enabled': False},
            ],
        }, format='json')
        assert res.status_code == 200
        by_type = {r['type']: r for r in res.json()['results']}
        assert by_type['PROMOTION']['enabled'] is False
        assert by_type['SUPPORT_UPDATE']['enabled'] is False
        assert NotificationPreference.objects.filter(
            user=user, type='PROMOTION', enabled=False,
        ).exists()
        assert NotificationPreference.objects.filter(
            user=user, type='SUPPORT_UPDATE', enabled=False,
        ).exists()

    def test_resave_is_idempotent(self, auth_client, user, db):
        """H-NOT-01: reguardar la misma preferencia no duplica filas ni rompe
        (el upsert tolerante actualiza en sitio, no crea una segunda fila)."""
        payload = {'preferences': [{'type': 'PROMOTION', 'enabled': False}]}
        assert auth_client.put(PREFERENCES_URL, payload, format='json').status_code == 200
        # segundo guardado: toggle de vuelta a True, sobre la fila existente
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'PROMOTION', 'enabled': True}],
        }, format='json')
        assert res.status_code == 200
        rows = NotificationPreference.objects.filter(user=user, type='PROMOTION')
        assert rows.count() == 1
        assert rows.first().enabled is True


# ─── GET /admin/audience-count ───────────────────────────────────────────
class TestAdminAudienceCount:
    def test_requires_auth(self, api_client, db):
        res = api_client.get(ADMIN_AUDIENCE_URL + '?recipient_type=USER')
        assert res.status_code == 401

    def test_requires_staff(self, auth_client, db):
        res = auth_client.get(ADMIN_AUDIENCE_URL + '?recipient_type=USER')
        assert res.status_code == 403

    def test_user_recipient_count_matches_username(self, admin_client, user, db):
        res = admin_client.get(
            ADMIN_AUDIENCE_URL + f'?recipient_type=USER&recipient_identifier={user.email}'
        )
        assert res.status_code == 200
        assert res.json() == {'count': 1}

    def test_user_recipient_count_zero_when_missing(self, admin_client, db):
        res = admin_client.get(
            ADMIN_AUDIENCE_URL + '?recipient_type=USER&recipient_identifier=nope-zzz'
        )
        assert res.status_code == 200
        assert res.json() == {'count': 0}

    def test_invalid_recipient_type_returns_400(self, admin_client, db):
        res = admin_client.get(ADMIN_AUDIENCE_URL + '?recipient_type=WHATEVER')
        assert res.status_code == 400

    def test_product_buyers_zero_when_no_orders(self, admin_client, db):
        res = admin_client.get(
            ADMIN_AUDIENCE_URL + '?recipient_type=PRODUCT_BUYERS&product_id=999999'
        )
        assert res.status_code == 200
        assert res.json() == {'count': 0}


# ─── POST /admin/manual ──────────────────────────────────────────────────
class TestAdminManualNotification:
    def test_requires_auth(self, api_client, db):
        res = api_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': 'nobody',
            'subject': 'Hola',
            'message': 'Mensaje suficientemente largo.',
        }, format='json')
        assert res.status_code == 401

    def test_requires_staff(self, auth_client, db):
        res = auth_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': 'nobody',
            'subject': 'Hola',
            'message': 'Mensaje suficientemente largo.',
        }, format='json')
        assert res.status_code == 403

    def test_send_to_specific_user_creates_notification(
        self, admin_client, user, db,
    ):
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': user.email,
            'subject': 'Hola directo',
            'message': 'Mensaje directo de prueba.',
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        for key in ('id', 'recipients_count', 'status'):
            assert key in body
        assert body['recipients_count'] == 1
        assert body['status'] == 'SENT'

        assert Notification.objects.filter(
            user=user, subject='Hola directo',
        ).count() == 1

    def test_user_without_identifier_returns_400(self, admin_client, db):
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'subject': 'Hola',
            'message': 'Mensaje de prueba.',
        }, format='json')
        assert res.status_code == 400

    def test_product_buyers_without_product_id_returns_400(self, admin_client, db):
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'PRODUCT_BUYERS',
            'subject': 'Hola',
            'message': 'Mensaje de prueba.',
        }, format='json')
        assert res.status_code == 400

    def test_send_to_user_who_disabled_promotion_skips_notification(
        self, admin_client, user, db,
    ):
        NotificationPreference.objects.create(
            user=user, type='PROMOTION', enabled=False,
        )
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': user.email,
            'subject': 'Promo bloqueada',
            'message': 'No deberia llegar.',
        }, format='json')
        assert res.status_code == 201
        # recipients_count refleja la audiencia bruta, no la entregada.
        assert res.json()['recipients_count'] == 1

        assert Notification.objects.filter(
            user=user, subject='Promo bloqueada',
        ).count() == 0
