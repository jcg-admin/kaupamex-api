"""
Tests unitarios del modelo User — PracticaYoruba API.

TDD: estos tests documentan el comportamiento esperado del modelo
ANTES de que exista la logica. Si el test pasa, el modelo cumple el contrato.

BD: practicayoruba_uta
"""
import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.unit

User = get_user_model()


class TestUserCreation:
    """El modelo User se puede crear con los campos minimos."""

    def test_create_user_with_username_and_password(self, db):
        user = User.objects.create_user(
            username='nestor',
            password='Pass1234!'
        )
        assert user.pk is not None
        assert user.username == 'nestor'
        assert user.is_active is True
        assert user.is_staff is False

    def test_create_user_stores_hashed_password(self, db):
        user = User.objects.create_user(username='nestor2', password='Pass1234!')
        assert user.password != 'Pass1234!'
        assert user.check_password('Pass1234!') is True

    def test_create_user_with_email(self, db):
        user = User.objects.create_user(
            username='nestor3',
            email='nestor@practicayoruba.mx',
            password='Pass1234!'
        )
        assert user.email == 'nestor@practicayoruba.mx'

    def test_user_str_returns_full_name_if_set(self, db):
        user = User.objects.create_user(
            username='nestor4',
            first_name='Nestor',
            last_name='Garcia',
            password='Pass1234!'
        )
        assert str(user) == 'Nestor Garcia'

    def test_user_str_fallback_to_username(self, db):
        user = User.objects.create_user(username='nestor5', password='Pass1234!')
        assert str(user) == 'nestor5'


class TestUserFields:
    """El modelo User tiene los campos extendidos definidos."""

    def test_user_has_phone_field(self, db):
        user = User.objects.create_user(
            username='nestor6',
            password='Pass1234!',
            phone='5512345678'
        )
        assert user.phone == '5512345678'

    def test_user_phone_blank_by_default(self, db):
        user = User.objects.create_user(username='nestor7', password='Pass1234!')
        assert user.phone == ''

    def test_user_avatar_null_by_default(self, db):
        user = User.objects.create_user(username='nestor8', password='Pass1234!')
        assert user.avatar.name is None

    def test_get_avatar_url_returns_none_without_avatar(self, db):
        user = User.objects.create_user(username='nestor9', password='Pass1234!')
        assert user.get_avatar_url() is None
