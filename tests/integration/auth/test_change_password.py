"""
Tests de integracion — Cambio de contrasena
UC-AUTH-08: Cambiar Contrasena
"""
import logging

import pytest
from apps.modules.users.models import AuthEvent
from apps.modules.users.tokens_email import invalidate_all_sessions
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.integration

CHANGE_URL = '/api/v2/auth/change-password/'
REFRESH_URL = '/api/v2/auth/refresh/'
PROFILE_URL = '/api/v2/auth/profile/'


class TestChangePassword:

    def test_cambio_exitoso_retorna_200(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200

    def test_contrasena_actual_incorrecta_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'PasswordIncorrecta!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 400

    def test_nueva_igual_a_actual_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'TestPass123!',
            'new_password_confirm': 'TestPass123!',
        }, format='json')
        assert r.status_code == 400

    def test_confirmacion_no_coincide_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'Diferente789#',
        }, format='json')
        assert r.status_code == 400

    def test_nueva_contrasena_demasiado_corta_retorna_400(self, auth_client, db):
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'corta',
            'new_password_confirm': 'corta',
        }, format='json')
        assert r.status_code == 400

    def test_sin_autenticar_retorna_401(self, api_client, db):
        r = api_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 401

    def test_nueva_contrasena_persiste(self, auth_client, user, db):
        auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        user.refresh_from_db()
        assert user.check_password('NuevoPass456@')

    def test_contrasena_antigua_ya_no_funciona(self, auth_client, user, db):
        auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        user.refresh_from_db()
        assert not user.check_password('TestPass123!')

    def test_change_password_invalida_sesiones_activas(
        self, auth_client, user, api_client, db,
    ):
        """UC-AUTH-08 PARTE 8.2 (DEC-AUM-01): tras change-password,
        los refresh tokens previos quedan blacklisted. Vector
        account-takeover post-password-change cerrado."""
        # Crear 2 refresh tokens activos para el user (sesiones
        # distintas en multiples dispositivos).
        refresh_a = str(RefreshToken.for_user(user))
        refresh_b = str(RefreshToken.for_user(user))
        # Ejecutar change-password.
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200
        # Verificar que AMBOS refresh tokens previos quedan
        # invalidados (blacklisteados) — no pueden renovar.
        for refresh_str in (refresh_a, refresh_b):
            res = api_client.post(
                REFRESH_URL, {'refresh': refresh_str}, format='json',
            )
            assert res.status_code == 401, (
                f'refresh_str debio quedar blacklisted, status {res.status_code}'
            )

    @pytest.mark.django_db(transaction=True)
    def test_change_password_emits_audit_event(
        self, auth_client, user,
    ):
        """T-119 D-02 iter 20 (UC-AUTH-08 AC-06): change-password
        registra evento PASSWORD_CHANGE en AuthEvent. Antes el
        cambio era silencioso (sin trazabilidad GDPR / forense).

        Requiere transaction=True porque audit_log_auth usa
        transaction.on_commit (no se ejecuta con rollback default)."""
        AuthEvent.objects.filter(user=user).delete()
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200
        events = AuthEvent.objects.filter(
            user=user, action=AuthEvent.ACTION_PASSWORD_CHANGE,
        )
        assert events.count() == 1, (
            f'PASSWORD_CHANGE debio emitirse, encontrado: '
            f'{[e.action for e in AuthEvent.objects.filter(user=user)]}'
        )

    # ─── CR-3 (ADR-018 hotfix): la sesion actual NO debe cerrarse ──────────

    def test_change_password_conserva_sesion_actual(self, auth_client, db):
        """CR-3: quien cambia su contrasena conserva su sesion (patron
        nativo update_session_auth_hash); antes invalidate_all_sessions
        borraba tambien la sesion en curso -> logout inmediato."""
        assert auth_client.get(PROFILE_URL).status_code == 200
        r = auth_client.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200
        # La MISMA sesion sigue autenticada tras el cambio.
        assert auth_client.get(PROFILE_URL).status_code == 200

    def test_change_password_cierra_las_otras_sesiones(self, user, db):
        """CR-3: las OTRAS sesiones del usuario si se cierran (revocacion),
        solo se preserva la del request en curso."""
        c_actual = APIClient()
        c_actual.force_login(user)
        c_otra = APIClient()
        c_otra.force_login(user)
        assert c_otra.get(PROFILE_URL).status_code == 200

        r = c_actual.post(CHANGE_URL, {
            'current_password': 'TestPass123!',
            'new_password': 'NuevoPass456@',
            'new_password_confirm': 'NuevoPass456@',
        }, format='json')
        assert r.status_code == 200

        assert c_actual.get(PROFILE_URL).status_code == 200   # sobrevive
        assert c_otra.get(PROFILE_URL).status_code == 401      # revocada

    # ─── CR-4 (ADR-018 hotfix): sin ruido al reintentar tokens ya negros ───

    def test_invalidate_all_sessions_sin_ruido_de_tokens_blacklisteados(
        self, user, db, caplog,
    ):
        """CR-4: invalidate_all_sessions no debe loguear tracebacks al
        toparse con OutstandingToken que ya estan en BlacklistedToken
        (rotacion previa)."""
        rt = RefreshToken.for_user(user)
        rt.blacklist()  # queda en BlacklistedToken
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            invalidate_all_sessions(user)
        assert 'blacklist refresh token failed' not in caplog.text
