"""``res.users.settings`` — los cinco métodos que la referencia declara.

El archivo se declaraba *portación fiel* con **0 de 5** métodos portados: sólo
la FK y su constraint. Los cinco son el contrato del modelo — buscar-o-crear,
listar qué se formatea, formatear, y escribir devolviendo el diff — y
``_format_settings`` es además el enganche que Enterprise 19 extiende en dos
clases con ``_inherit = 'res.users.settings'``.

Referencia: ``odoo19c: odoo/addons/base/models/res_users_settings.py:20-55``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.res_users_settings import ResUsersSettings


pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        login='dueno.de.preferencias', password='X9v!kQ2mZr4t')


def test_the_blacklist_names_what_is_never_formatted():
    assert ResUsersSettings._get_fields_blacklist() == ['display_name']


def test_find_or_create_is_idempotent(user):
    primera = ResUsersSettings._find_or_create_for_user(user)
    segunda = ResUsersSettings._find_or_create_for_user(user)
    assert primera.pk == segunda.pk
    assert ResUsersSettings.objects.filter(user=user).count() == 1


def test_the_default_format_carries_id_and_the_user_reference(user):
    settings = ResUsersSettings._find_or_create_for_user(user)
    formatted = settings._res_users_settings_format()
    assert formatted['id'] == settings.pk
    assert formatted['user'] == {'id': user.pk}


def test_the_audit_columns_stay_out_of_the_default_format(user):
    """Las magic columns de la referencia son aquí ``created_at``/``updated_at``."""
    settings = ResUsersSettings._find_or_create_for_user(user)
    formatted = settings._res_users_settings_format()
    assert 'created_at' not in formatted
    assert 'updated_at' not in formatted


def test_an_explicit_list_wins_and_the_blacklist_still_applies(user):
    settings = ResUsersSettings._find_or_create_for_user(user)
    formatted = settings._res_users_settings_format(['id', 'display_name'])
    assert set(formatted) == {'id'}


def test_set_returns_only_what_changed_plus_the_id(user):
    settings = ResUsersSettings._find_or_create_for_user(user)
    assert settings.set_res_users_settings({}) == {'id': settings.pk}


def test_res_users_settings_format_goes_through_the_hook(user):
    """El control: sin el enganche en medio, la marca no llegaría."""
    settings = ResUsersSettings._find_or_create_for_user(user)
    original = ResUsersSettings._format_settings

    def marked(self, fields_to_format):
        values = original(self, fields_to_format)
        values['marca'] = True
        return values

    ResUsersSettings._format_settings = marked
    try:
        assert settings._res_users_settings_format().get('marca') is True
    finally:
        ResUsersSettings._format_settings = original
