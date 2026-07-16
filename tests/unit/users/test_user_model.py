"""
Tests unitarios del modelo de identidad — PracticaYoruba API (party, T-201).

IdentityUser (U-D puro) es sólo email + credenciales; nombre/teléfono/avatar
viven en Person. El email es el identificador (USERNAME_FIELD).

BD: practicayoruba_qa
"""
import pytest
from django.contrib.auth import get_user_model

from apps.modules.users.models import Person

pytestmark = pytest.mark.unit

User = get_user_model()


class TestIdentityCreation:
    """La identidad se crea con email + password (sin username)."""

    def test_create_user_requires_email(self, db):
        with pytest.raises(ValueError):
            User.objects.create_user(email='', password='Pass1234!')

    def test_create_user_with_email(self, db):
        user = User.objects.create_user(
            email='nestor@practicayoruba.mx', password='Pass1234!',
        )
        assert user.pk is not None
        assert user.email == 'nestor@practicayoruba.mx'
        assert user.is_active is True

    def test_username_field_is_email(self, db):
        assert User.USERNAME_FIELD == 'email'

    def test_create_user_stores_hashed_password(self, db):
        user = User.objects.create_user(
            email='a@practicayoruba.mx', password='Pass1234!',
        )
        assert user.password != 'Pass1234!'
        assert user.check_password('Pass1234!') is True

    def test_str_returns_email(self, db):
        user = User.objects.create_user(
            email='str@practicayoruba.mx', password='Pass1234!',
        )
        assert str(user) == 'str@practicayoruba.mx'


class TestPartyAccessors:
    """first_name/last_name/phone son accesores de solo lectura que delegan a
    Person; el avatar también vive en Person."""

    def test_name_accessors_empty_without_person(self, db):
        user = User.objects.create_user(
            email='np@practicayoruba.mx', password='Pass1234!',
        )
        assert user.first_name == ''
        assert user.last_name == ''
        assert user.phone == ''
        assert user.get_full_name() == ''

    def test_name_accessors_delegate_to_person(self, db):
        user = User.objects.create_user(
            email='wp@practicayoruba.mx', password='Pass1234!',
        )
        Person.objects.create(
            identity=user, first_name='Nestor', last_name='Garcia',
            phone='5512345678',
        )
        assert user.first_name == 'Nestor'
        assert user.last_name == 'Garcia'
        assert user.phone == '5512345678'
        assert user.get_full_name() == 'Nestor Garcia'

    def test_get_avatar_url_returns_none_without_avatar(self, db):
        user = User.objects.create_user(
            email='av@practicayoruba.mx', password='Pass1234!',
        )
        assert user.get_avatar_url() is None
