"""Tests — eje interno/portal/público de ``res.users``.

Verifica ``_is_internal()``/``_is_portal()``/``_is_public()``/``share``,
adaptación de ``_is_internal``/``_compute_share`` de la referencia
(``odoo19c: odoo/addons/base/models/res_users.py:460-464,1165-1179``) al
modelo ``user_type``-en-grupo de este árbol (``res_groups.py``).
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.res_groups import ResGroups

User = get_user_model()


@pytest.fixture
def grupos(db):
    interno = ResGroups.objects.create(
        name='Internos', user_type=ResGroups.USER_TYPE_INTERNAL)
    portal = ResGroups.objects.create(
        name='Portal', user_type=ResGroups.USER_TYPE_PORTAL)
    public = ResGroups.objects.create(
        name='Público', user_type=ResGroups.USER_TYPE_PUBLIC)
    return interno, portal, public


def _user(login):
    return User.objects.create_user(login=login)


class TestUserTypeAxis:

    def test_interno(self, grupos):
        interno, _p, _pu = grupos
        u = _user('empleado@kaupamex.mx')
        interno.user_ids.add(u)
        assert u._is_internal() is True
        assert u._is_portal() is False
        assert u.share is False

    def test_portal(self, grupos):
        _i, portal, _pu = grupos
        u = _user('cliente@kaupamex.mx')
        portal.user_ids.add(u)
        assert u._is_portal() is True
        assert u._is_internal() is False
        assert u.share is True

    def test_public(self, grupos):
        _i, _p, public = grupos
        u = _user('anon@kaupamex.mx')
        public.user_ids.add(u)
        assert u._is_public() is True
        assert u.share is True

    def test_sin_grupo_de_tipo_es_share(self, db):
        # Sin ningún grupo de tipo, share=True (todo lo no-interno, ≙
        # _compute_share de la referencia).
        u = _user('sin-grupo@kaupamex.mx')
        assert u._is_internal() is False
        assert u.share is True
