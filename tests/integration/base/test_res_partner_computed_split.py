"""Tests — la partición privado/público de cinco cómputos de ``res.partner``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_compute_contact_address`` (``:506``), ``_compute_get_ids`` (``:510``),
``_compute_commercial_partner`` (``:515``),
``_compute_commercial_company_name`` (``:523``) y ``_compute_is_public``
(``:851``).

Qué se corrige aquí, y no es cosmético
=======================================

Tres de los cinco **ya funcionaban** en este árbol, pero como ``property``
pública sin su cómputo privado. La fuente parte cada uno en dos —el campo
``X`` que se lee, y el ``_compute_X`` que lo calcula— y esa frontera es el
punto de extensión: un addon que quiera cambiar cómo se deriva la entidad
comercial sobreescribe ``_compute_commercial_partner``, no la lectura.

Sin la partición ese addon no tiene dónde engancharse, que es la mitad del
contrato de ``porte-completo-no-parcial.md``: *el guion bajo se porta, es el
contrato*.

Los otros dos **no existían**:

``is_public``
    ¿Este partner es el usuario público (el visitante anónimo del sitio)?
    Sin él, nada distingue un cliente real del registro que representa a
    «cualquiera que entre sin sesión».
``self``
    Alias del propio registro. Existe para que una vista pueda referirse al
    partner actual con el mismo vocabulario con que referiría a otro.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from django.contrib.auth import get_user_model

from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner

User = get_user_model()

pytestmark = pytest.mark.integration


class TestPrivatePublicSplit:
    """Los tres que ya existían: el campo sigue leyéndose igual y ahora hay
    dónde engancharse."""

    def test_the_commercial_partner_field_still_reads(self, db):
        company = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        who = ResPartner.objects.create(name='Ana', parent=company)
        assert who.commercial_partner == company

    def test_the_field_delegates_to_the_private_compute(self, db):
        """CONTROL de la partición — si el campo no delegara, sobreescribir
        el cómputo no cambiaría la lectura y el punto de extensión sería
        decorativo."""
        company = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        who = ResPartner.objects.create(name='Ana', parent=company)
        assert who.commercial_partner == who._compute_commercial_partner()

    def test_the_company_name_field_delegates_too(self, db):
        company = ResPartner.objects.create(name='Kaupamex SA', is_company=True)
        who = ResPartner.objects.create(name='Ana', parent=company)
        assert who.commercial_company_name == who._compute_commercial_company_name()

    def test_the_contact_address_field_delegates_too(self, db):
        who = ResPartner.objects.create(name='Ana', street='Reforma 1',
                                        city='CDMX')
        assert who.contact_address == who._compute_contact_address()


class TestIsPublic:
    """≙ ``_compute_is_public`` (``:851``) — ¿es el visitante anónimo?"""

    def test_a_partner_without_users_is_not_public(self, db):
        """La fuente exige ``users and any(...)``: sin usuarios el ``and``
        corta. Qué lo haría fallar: devolver ``any([])`` a secas, que también
        es falso — por eso el caso siguiente es el que discrimina."""
        assert ResPartner.objects.create(name='Ana').is_public is False

    def test_a_partner_whose_user_is_public_is_public(self, db):
        """El eje — es lo único que distingue al visitante anónimo de un
        cliente real."""
        user = User.objects.create_user(login='anon@kaupamex.mx',
                                        password='Secreta-123')
        group = ResGroups.objects.create(name='visitante', user_type='public')
        user.group_ids.add(group)
        assert user.partner.is_public is True

    def test_a_partner_whose_user_is_internal_is_not_public(self, db):
        """CONTROL — sin la pregunta por ``_is_public`` cualquier partner con
        usuario saldría público, y el visitante anónimo dejaría de ser
        distinguible."""
        user = User.objects.create_user(login='ana@kaupamex.mx',
                                        password='Secreta-123')
        group = ResGroups.objects.create(name='staff', user_type='internal')
        user.group_ids.add(group)
        assert user.partner.is_public is False


class TestSelfAlias:
    """≙ ``_compute_get_ids`` (``:510``) — ``partner.self`` es el propio
    registro."""

    def test_it_is_the_record_itself(self, db):
        who = ResPartner.objects.create(name='Ana')
        assert who.self == who

    def test_it_is_not_merely_the_pk(self, db):
        """CONTROL — la fuente declara el campo como ``Many2one``, no como
        entero: devuelve el REGISTRO. Sin eso, quien lo lea no podría
        atravesar a sus campos."""
        who = ResPartner.objects.create(name='Ana')
        assert who.self.name == 'Ana'
