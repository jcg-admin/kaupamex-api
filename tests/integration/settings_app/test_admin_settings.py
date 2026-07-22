"""
Tests de integracion — Admin SiteSettings (UC-ADM-04)
T-119: SiteSettingsView — GET/PATCH /api/v2/admin/settings/
T-008 (H-API-NN): PATCH debe emitir BusinessEvent para el audit
log de UC-ADM-03 — sin este registro, un cambio de configuracion
es invisible en /api/v2/admin/audit-log/.
"""
import pytest
from addons.base.models import SiteSettings
from addons.users.models import BusinessEvent

pytestmark = pytest.mark.integration

SETTINGS_URL = '/api/v2/admin/settings/'


@pytest.fixture
def site_settings(db):
    return SiteSettings.get_or_create_defaults()


class TestAdminSiteSettings:

    def test_admin_puede_ver_settings(self, admin_auth_client, site_settings, db):
        r = admin_auth_client.get(SETTINGS_URL)
        assert r.status_code == 200

    def test_comprador_no_puede_ver_settings(self, auth_client, site_settings, db):
        r = auth_client.get(SETTINGS_URL)
        assert r.status_code == 403

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.get(SETTINGS_URL)
        assert r.status_code == 401

    def test_campos_retornados(self, admin_auth_client, site_settings, db):
        r = admin_auth_client.get(SETTINGS_URL)
        data = r.json()
        for field in ['site_name', 'iva_rate', 'currency', 'max_return_days']:
            assert field in data

    def test_admin_puede_actualizar_settings(self, admin_auth_client, site_settings, db):
        r = admin_auth_client.patch(
            SETTINGS_URL,
            {'max_return_days': 45},
            format='json',
        )
        assert r.status_code == 200
        assert r.json()['max_return_days'] == 45

    def test_comprador_no_puede_actualizar_settings(self, auth_client, site_settings, db):
        r = auth_client.patch(
            SETTINGS_URL,
            {'max_return_days': 99},
            format='json',
        )
        assert r.status_code == 403

    def test_actualizar_settings_crea_business_event(
        self, admin_auth_client, admin_user, site_settings, db,
        django_capture_on_commit_callbacks,
    ):
        """H-API-NN: sin este registro el cambio no aparece en el
        audit log de UC-ADM-03 (AuditLogView combina AuthEvent +
        BusinessEvent + UserDeactivationEvent).

        audit_log_business emite el BusinessEvent vía transaction.on_commit
        (DEC-CC-2); en el atomic-rollback default del test los callbacks no
        disparan, así que se capturan/ejecutan explícitamente (mismo patrón
        que test_admin_user_actions.py::test_cambio_se_audita_en_business_event).
        """
        assert BusinessEvent.objects.count() == 0

        with django_capture_on_commit_callbacks(execute=True):
            r = admin_auth_client.patch(
                SETTINGS_URL,
                {'max_return_days': 45},
                format='json',
            )
        assert r.status_code == 200

        assert BusinessEvent.objects.count() == 1
        event = BusinessEvent.objects.get()
        assert event.actor_id == admin_user.pk
        assert event.action == 'ADMIN_SETTINGS_UPDATED'
        assert event.target_type == 'site_settings'
        assert event.target_id == site_settings.pk
        assert 'max_return_days' in event.extra_json.get('changes', {})
