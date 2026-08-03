"""Tests — addons.portal (núcleo Python).

Cubre lo portado en este pase (``odoo19c: portal/``, leído completo):

- ``document_check_access`` (≙ ``_document_check_access``, portal.py:961-980):
  el token concede acceso en tiempo constante cuando el permiso normal no.
- las reglas de edición del partner por portal/público
  (``portal/models/res_partner.py``), sobre el eje ``is_public()``/
  ``is_internal()`` real (H-API-234).

``PortalMixin`` es abstracto (sin tabla): su aplicación a un documento
concreto (``SaleOrder``) es la decisión siguiente del loop — por eso su
``_portal_ensure_token``/``get_portal_url`` se ejercen ahí, no aquí.
"""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from exceptions import AccessDenied, MissingError

from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner
from addons.portal.models import res_partner as pp
from addons.portal.services import document_check_access

User = get_user_model()


class _FakeManager:
    """Emula ``model.objects``: filter(pk=...).first()."""

    def __init__(self, rows):
        self._rows = {r.pk: r for r in rows}

    def filter(self, pk=None):
        row = self._rows.get(pk)
        return SimpleNamespace(first=lambda: row)


class _FakeModel:
    def __init__(self, rows):
        self.objects = _FakeManager(rows)


class TestDocumentCheckAccess:
    """≙ ``_document_check_access`` (portal.py:961-980)."""

    def _doc(self, pk, token):
        return SimpleNamespace(pk=pk, access_token=token)

    def test_token_correcto_concede(self):
        doc = self._doc(1, 'tok-abc')
        model = _FakeModel([doc])
        got = document_check_access(
            model, 1, user=None, access_token='tok-abc',
            can_read=lambda d, u: False)
        assert got is doc

    def test_token_incorrecto_niega(self):
        doc = self._doc(1, 'tok-abc')
        model = _FakeModel([doc])
        with pytest.raises(AccessDenied):
            document_check_access(
                model, 1, user=None, access_token='tok-xxx',
                can_read=lambda d, u: False)

    def test_permiso_normal_concede_sin_token(self):
        doc = self._doc(1, 'tok-abc')
        model = _FakeModel([doc])
        got = document_check_access(
            model, 1, user='alguien', access_token=None,
            can_read=lambda d, u: True)
        assert got is doc

    def test_documento_inexistente(self):
        model = _FakeModel([])
        with pytest.raises(MissingError):
            document_check_access(
                model, 99, user=None, access_token='x',
                can_read=lambda d, u: True)

    def test_sin_token_ni_permiso_niega(self):
        doc = self._doc(1, '')  # documento sin token emitido
        model = _FakeModel([doc])
        with pytest.raises(AccessDenied):
            document_check_access(
                model, 1, user=None, access_token=None,
                can_read=lambda d, u: False)


class TestPartnerFrontendRules:
    """≙ ``portal/models/res_partner.py``."""

    @pytest.fixture
    def internos(self, db):
        return ResGroups.objects.create(
            name='Internos', user_type=ResGroups.USER_TYPE_INTERNAL)

    @pytest.fixture
    def publicos(self, db):
        return ResGroups.objects.create(
            name='Público', user_type=ResGroups.USER_TYPE_PUBLIC)

    def test_current_partner_de_publico_es_none(self, publicos):
        u = User.objects.create_user(login='anon@kaupamex.mx')
        publicos.user_ids.add(u)
        assert pp.current_partner(u) is None

    def test_current_partner_de_no_publico(self, db):
        u = User.objects.create_user(login='cli@kaupamex.mx')
        assert pp.current_partner(u) == u.partner

    def test_can_edit_vat_solo_entidad_comercial(self, db):
        matriz = ResPartner.objects.create(name='Matriz SA')
        hija = ResPartner.objects.create(
            name='Sucursal', parent=matriz,
            type=ResPartner.TYPE_INVOICE)
        assert pp.can_edit_vat(matriz) is True
        assert pp.can_edit_vat(hija) is False

    def test_can_be_edited_by_propio_y_no_ajeno(self, db):
        u = User.objects.create_user(login='dueno@kaupamex.mx')
        propio = u.partner
        ajeno = ResPartner.objects.create(name='Otro')
        assert pp.can_be_edited_by(propio, u) is True
        assert pp.can_be_edited_by(ajeno, u) is False

    def test_can_be_edited_by_hijo_direccion(self, db):
        u = User.objects.create_user(login='comercial@kaupamex.mx')
        # La dirección de envío del propio partner es editable.
        envio = ResPartner.objects.create(
            name='Envío', parent=u.partner,
            type=ResPartner.TYPE_DELIVERY)
        assert pp.can_be_edited_by(envio, u) is True

    def test_publico_no_edita_nada(self, publicos):
        u = User.objects.create_user(login='anon2@kaupamex.mx')
        publicos.user_ids.add(u)
        alguien = ResPartner.objects.create(name='X')
        assert pp.can_be_edited_by(alguien, u) is False
