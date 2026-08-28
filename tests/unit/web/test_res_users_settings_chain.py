"""``web`` extiende ``_format_settings`` — y su resultado se SUMA al de base.

La referencia lo escribe con ``super()``::

    def _format_settings(self, fields_to_format):
        res = super()._format_settings(fields_to_format)          # web:10
        if 'embedded_actions_config_ids' in fields_to_format:
            res['embedded_actions_config_ids'] = ...
        return res

Aquí el ``_inherit`` se materializa con ``chain_method``, cuyo relevo por
defecto **no** invoca la previa cuando la nueva devuelve algo distinto de
``None``. Un diccionario vacío no es ``None``: sin ``combine`` el eslabón de
``web`` descarta las claves de base y el formato pierde ``id`` y ``user``.

Referencia: ``odoo19c: addons/web/models/res_users_settings.py:9-14``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.res_users_settings import ResUsersSettings
from addons.web.models.res_users_settings_embedded_action import (
    ResUsersSettingsEmbeddedAction,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def settings():
    user = get_user_model().objects.create_user(
        login='dueno.de.acciones.embebidas', password='X9v!kQ2mZr4t')
    return ResUsersSettings._find_or_create_for_user(user)


def test_the_web_link_keeps_the_keys_that_base_contributes(settings):
    """El control de composición: sin encadenar, ``id`` y ``user`` no llegan."""
    formatted = settings._format_settings(['id', 'user'])
    assert formatted['id'] == settings.pk
    assert formatted['user'] == {'id': settings.user_id}


def test_the_web_link_adds_its_own_key_on_top(settings):
    action = IrActionsActWindow.objects.create(
        name='Ventas embebidas', res_model='sale.SaleOrder')
    ResUsersSettingsEmbeddedAction.objects.create(
        user_setting_id=settings, action_id_id=action.pk, res_id=1,
        embedded_actions_order='7,false', embedded_actions_visibility='7')

    formatted = settings._format_settings(
        ['id', 'embedded_actions_config_ids'])

    assert formatted['id'] == settings.pk
    assert formatted['embedded_actions_config_ids']


def test_the_default_format_reaches_the_relation_that_web_contributes(settings):
    """``_fields`` de la referencia incluye el One2many; aquí lo aporta el
    ``related_name`` del modelo hijo, y ``concrete_fields`` no lo ve."""
    formatted = settings._res_users_settings_format()
    assert 'embedded_actions_config_ids' in formatted
