"""
Tests — Notifications endpoints (UC-NOT-01..07)

Reads:
  GET  /api/v1/notifications/                    list
  GET  /api/v1/notifications/unread-count/       unread count
  GET  /api/v1/notifications/preferences/        list preferences
  GET  /api/v1/admin/notifications/audience-count/ audience size

Mutations:
  POST /api/v1/notifications/{id}/read/          mark one as read
  POST /api/v1/notifications/read-all/           mark all as read
  PUT  /api/v1/notifications/preferences/        update preferences
  POST /api/v1/admin/notifications/manual/       send manual

JSON keys + identifiers in English (DEC-DOC-005).
"""
import pytest

pytestmark = pytest.mark.integration

LIST_URL = '/api/v1/notifications/'
UNREAD_COUNT_URL = '/api/v1/notifications/unread-count/'
READ_ALL_URL = '/api/v1/notifications/read-all/'
PREFERENCES_URL = '/api/v1/notifications/preferences/'
ADMIN_AUDIENCE_URL = '/api/v1/admin/notifications/audience-count/'
ADMIN_MANUAL_URL = '/api/v1/admin/notifications/manual/'


# ─── helpers ─────────────────────────────────────────────────────────────
def _make_notification(user, **kwargs):
    from apps.notifications.models import Notification
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
        for key in ('id', 'type', 'subject', 'body', 'read', 'created_at'):
            assert key in item

    def test_returns_empty_results_when_none(self, auth_client, db):
        res = auth_client.get(LIST_URL)
        assert res.status_code == 200
        assert res.json() == {'results': []}


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
        res = api_client.post(f'{LIST_URL}{notif.pk}/read/')
        assert res.status_code == 401

    def test_marks_own_notification_as_read(self, auth_client, user, db):
        notif = _make_notification(user, read=False)
        res = auth_client.post(f'{LIST_URL}{notif.pk}/read/')
        assert res.status_code == 200
        notif.refresh_from_db()
        assert notif.read is True

    def test_returns_404_for_other_user(self, auth_client, admin_user, db):
        notif = _make_notification(admin_user)
        res = auth_client.post(f'{LIST_URL}{notif.pk}/read/')
        assert res.status_code == 404

    def test_returns_404_for_missing(self, auth_client, db):
        res = auth_client.post(f'{LIST_URL}999999/read/')
        assert res.status_code == 404


# ─── POST /read-all ──────────────────────────────────────────────────────
class TestMarkAllRead:
    def test_requires_auth(self, api_client, db):
        res = api_client.post(READ_ALL_URL)
        assert res.status_code == 401

    def test_marks_all_user_notifications_as_read(self, auth_client, user, admin_user, db):
        _make_notification(user, read=False)
        _make_notification(user, read=False)
        other = _make_notification(admin_user, read=False)
        res = auth_client.post(READ_ALL_URL)
        assert res.status_code == 200
        assert res.json()['updated'] == 2

        from apps.notifications.models import Notification
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

        from apps.notifications.models import NotificationPreference
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

    def test_invalid_type_returns_400(self, auth_client, db):
        res = auth_client.put(PREFERENCES_URL, {
            'preferences': [{'type': 'BOGUS', 'enabled': False}],
        }, format='json')
        assert res.status_code == 400


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
            ADMIN_AUDIENCE_URL + f'?recipient_type=USER&recipient_identifier={user.username}'
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
            'recipient_identifier': user.username,
            'subject': 'Hola directo',
            'message': 'Mensaje directo de prueba.',
        }, format='json')
        assert res.status_code == 201
        body = res.json()
        for key in ('id', 'recipients_count', 'status'):
            assert key in body
        assert body['recipients_count'] == 1
        assert body['status'] == 'SENT'

        from apps.notifications.models import Notification
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
        from apps.notifications.models import NotificationPreference
        NotificationPreference.objects.create(
            user=user, type='PROMOTION', enabled=False,
        )
        res = admin_client.post(ADMIN_MANUAL_URL, {
            'recipient_type': 'USER',
            'recipient_identifier': user.username,
            'subject': 'Promo bloqueada',
            'message': 'No deberia llegar.',
        }, format='json')
        assert res.status_code == 201
        # recipients_count refleja la audiencia bruta, no la entregada.
        assert res.json()['recipients_count'] == 1

        from apps.notifications.models import Notification
        assert Notification.objects.filter(
            user=user, subject='Promo bloqueada',
        ).count() == 0
