"""
Tests unitarios del management command create_seed_users.

BD: practicayoruba_qa (config.settings.testing)
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.unit

User = get_user_model()

_VALID_ENV = {
    'ADMIN_EMAIL': 'admin@practicayoruba.mx',
    'ADMIN_USERNAME': 'admin',
    'ADMIN_PASSWORD': 'AdminPass123!',
    'QA_BUYER_EMAIL': 'qabuyer@practicayoruba.mx',
    'QA_BUYER_PASSWORD': 'QABuyerPass123!',
}


class TestCreateSeedUsersAdmin:
    """El command crea el superusuario admin con los flags correctos."""

    def test_admin_created_with_correct_flags(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')

        # H-E2E-03: username == email (el login SPA autentica por username y
        # el form manda el email; el seed debe espejar el registro real).
        admin = User.objects.get(email='admin@practicayoruba.mx')
        assert admin.username == 'admin@practicayoruba.mx'
        assert admin.is_staff is True
        assert admin.is_superuser is True
        assert admin.is_active is True
        assert admin.deactivated_reason is None
        assert admin.deactivated_at is None

    def test_admin_password_hashed(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')

        admin = User.objects.get(email='admin@practicayoruba.mx')
        assert admin.password != _VALID_ENV['ADMIN_PASSWORD']
        assert admin.check_password(_VALID_ENV['ADMIN_PASSWORD']) is True


class TestCreateSeedUsersQABuyer:
    """El command crea el comprador QA activo y sin flags de staff."""

    def test_qa_buyer_created_with_correct_flags(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')

        buyer = User.objects.get(email='qabuyer@practicayoruba.mx')
        assert buyer.username == 'qabuyer@practicayoruba.mx'
        assert buyer.is_staff is False
        assert buyer.is_superuser is False
        assert buyer.is_active is True
        assert buyer.deactivated_reason is None
        assert buyer.deactivated_at is None

    def test_qa_buyer_password_hashed(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')

        buyer = User.objects.get(email='qabuyer@practicayoruba.mx')
        assert buyer.check_password(_VALID_ENV['QA_BUYER_PASSWORD']) is True


class TestCreateSeedUsersIdempotent:
    """El command es idempotente: ejecutarlo dos veces no produce error."""

    def test_second_call_exits_zero(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')
        # Segunda llamada no debe levantar excepción
        call_command('create_seed_users')

    def test_second_call_no_duplicate_keeps_username_email(self, db, monkeypatch):
        # H-E2E-03: el seed se identifica por email (username == email). Una
        # segunda corrida con el mismo email NO duplica y conserva la invariante.
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')
        call_command('create_seed_users')

        admins = User.objects.filter(email='admin@practicayoruba.mx')
        assert admins.count() == 1
        assert admins.first().username == 'admin@practicayoruba.mx'

    def test_idempotent_keeps_is_active_true(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users')
        # Simulación: alguien desactiva el admin manualmente
        User.objects.filter(email='admin@practicayoruba.mx').update(is_active=False)

        # Segunda llamada reactiva la cuenta
        call_command('create_seed_users')

        admin = User.objects.get(email='admin@practicayoruba.mx')
        assert admin.is_active is True


class TestCreateSeedUsersMissingVars:
    """El command falla con mensaje claro si faltan variables de entorno."""

    def test_missing_admin_password_raises_command_error(self, db, monkeypatch):
        env = {k: v for k, v in _VALID_ENV.items() if k != 'ADMIN_PASSWORD'}
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
        # El comando lee de os.environ Y de .env (decouple). Neutralizar el
        # fallback decouple para simular "ausente en TODO el entorno", no solo
        # en os.environ — si no, el .env del repo provee el valor. (H-API-04)
        monkeypatch.setattr('decouple.config', lambda option, default=None, **kw: default)

        with pytest.raises(CommandError) as exc_info:
            call_command('create_seed_users')

        assert 'ADMIN_PASSWORD' in str(exc_info.value)

    def test_missing_multiple_vars_lists_all(self, db, monkeypatch):
        monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
        monkeypatch.delenv('QA_BUYER_PASSWORD', raising=False)
        monkeypatch.delenv('ADMIN_EMAIL', raising=False)
        monkeypatch.delenv('ADMIN_USERNAME', raising=False)
        monkeypatch.delenv('QA_BUYER_EMAIL', raising=False)
        monkeypatch.setattr('decouple.config', lambda option, default=None, **kw: default)

        with pytest.raises(CommandError) as exc_info:
            call_command('create_seed_users')

        error_msg = str(exc_info.value)
        assert 'ADMIN_PASSWORD' in error_msg
        assert 'QA_BUYER_PASSWORD' in error_msg


class TestCreateSeedUsersDryRun:
    """El flag --dry-run no escribe en la base de datos."""

    def test_dry_run_does_not_create_users(self, db, monkeypatch):
        for k, v in _VALID_ENV.items():
            monkeypatch.setenv(k, v)

        call_command('create_seed_users', dry_run=True)

        assert not User.objects.filter(email='admin@practicayoruba.mx').exists()
        assert not User.objects.filter(email='qabuyer@practicayoruba.mx').exists()
