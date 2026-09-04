"""Declarar ``related=`` — el cableado del mecanismo al arranque (#252).

:ref:`h-api-974` porto ``setup_related`` y ``_search_related`` con sus
controles, y dejo el mecanismo **sin receptor**: medido entonces,
``fields.Char(related='a.b')`` levantaba ``TypeError`` —el constructor no
conoce la clave— y nadie llamaba a ``field.setup(model)``.

Este archivo fija las tres piezas que lo cierran:

1. el constructor acepta ``related=`` y aplica los cuatro defectos que la
   fuente le da (``odoo19c: odoo/orm/fields.py:452-458``);
2. leer el atributo navega la cadena;
3. buscar por el campo emite el dominio sobre la cadena, que es lo que
   navegar la FK a mano no da.
"""
import pytest
from django.apps import apps
from django.db import models

import fields
from orm.domains import Domain, DomainCondition
from orm.fields_nonstored import NonStored


class TestTheConstructorAcceptsTheDeclaration:
    """``:452-458`` — «by default, related fields are not stored, computed in
    superuser mode, not copied and readonly»."""

    def test_the_facade_accepts_related(self):
        field = fields.Char('Country Code', related='country.code')
        assert field.related == 'country.code'

    def test_a_related_is_not_stored_by_default(self):
        """``:455`` — ``attrs['store'] = attrs.get('store', False)``.

        Es el defecto que explica la forma de **552 de los 597** que la
        referencia declara. Sin columna, el portador es :class:`NonStored`.
        """
        field = fields.Char(related='country.code')
        assert isinstance(field, NonStored), type(field).__name__
        assert field.store is False

    def test_an_explicit_store_keeps_the_column(self):
        """``attrs.get('store', False)`` respeta lo declarado — el caso de los
        45 restantes. Es el control que discrimina al anterior."""
        field = fields.Char(related='country.code', store=True, max_length=8)
        assert isinstance(field, models.CharField), type(field).__name__
        assert field.store is True

    def test_the_other_three_defaults_of_the_source(self):
        """``:456-458`` — ``compute_sudo`` verdadero, ``copy`` falso,
        ``readonly`` verdadero."""
        field = fields.Char(related='country.code')
        assert field.compute_sudo is True
        assert field.copy is False
        assert field.readonly is True

    def test_what_the_declaration_says_wins_over_the_default(self):
        field = fields.Char(related='country.code', readonly=False, copy=True)
        assert field.readonly is False
        assert field.copy is True

    def test_the_dispatcher_family_accepts_it_too(self):
        """``make_dispatcher`` fabrica cinco constructores; el mecanismo es
        del campo, no del tipo, así que ninguno puede quedarse fuera."""
        for constructor in (fields.Boolean, fields.Integer, fields.Float,
                            fields.Text, fields.Selection):
            field = constructor(related='partner.name')
            assert field.related == 'partner.name', constructor.__name__
            assert isinstance(field, NonStored), constructor.__name__


class TestReadingWalksTheChain:
    """El ``compute`` del related — ``:675`` ``_compute_related``."""

    @pytest.fixture
    def bank(self, db):
        # ``get_or_create``: el catálogo de países viene sembrado y ``code``
        # es único, así que crearlo a ciegas choca con la fila real. El
        # related se lee igual sobre la sembrada — es la fila que el producto
        # usa.
        country, _created = apps.get_model('base', 'ResCountry').objects\
            .get_or_create(code='MX', defaults={'name': 'México'})
        return apps.get_model('base', 'ResBank').objects.create(
            name='Banco de prueba', country=country)

    def test_reading_the_related_gives_the_value_at_the_end(self, bank):
        assert bank.country_code == 'MX'

    def test_a_broken_link_reads_as_empty_instead_of_raising(self, db):
        """Un eslabón vacío no revienta: la fila sin país lee el valor falsy.

        La fuente hace lo mismo — ``_compute_related`` toma
        ``next(iter(corecord), corecord)``, y sobre un recordset vacío eso da
        el propio vacío, no un ``AttributeError``.
        """
        bank = apps.get_model('base', 'ResBank').objects.create(
            name='Sin país')
        assert not bank.country_code


class TestSearchingUsesTheChain:
    """Lo que navegar la FK a mano NO da — la razón por la que el campo se
    porta en vez de declinarse (:ref:`h-api-974`)."""

    def test_the_field_carries_its_search(self):
        field = fields.Char(related='country.code')
        assert field.search is not None, (
            'sin search el related se lee y no se filtra, que es exactamente '
            'lo que se perdía al navegarlo por la FK')

    def test_the_search_emits_the_domain_over_the_chain(self):
        bank = apps.get_model('base', 'ResBank')
        field = fields.Char(related='country.code')
        field.name = 'country_code'

        domain = field.search(bank, '=', 'MX')

        assert isinstance(domain, DomainCondition)
        assert domain.field_expr == 'country'
        assert domain.operator in ('any', 'any!')


class TestTheFourDeclaredInResBank:
    """Los cuatro ``related`` que ``res_bank.py`` declinaba, ya declarados.

    ``odoo19c: res_bank.py:29`` (``ResBank.country_code``), ``:97``
    (``bank_name``), ``:98`` (``bank_bic``) y ``:102``
    (``ResPartnerBank.country_code``). Ninguno lleva ``store`` en la fuente, así
    que ninguno ocupa columna aquí — lo confirma ``makemigrations base --check``.
    """

    @pytest.fixture
    def account(self, db):
        def base(name):
            return apps.get_model('base', name)

        country, _creada = base('ResCountry').objects.get_or_create(
            code='MX', defaults={'name': 'México'})
        bank = base('ResBank').objects.create(
            name='Banco de prueba', bic='BDPMMXMM', country=country)
        partner = base('ResPartner').objects.create(
            name='Titular de prueba', country=country)
        return base('ResPartnerBank').objects.create(
            acc_number='0123456789', partner=partner, bank=bank)

    def test_the_account_reads_the_name_and_the_bic_of_its_bank(self, account):
        assert account.bank_name == 'Banco de prueba'
        assert account.bank_bic == 'BDPMMXMM'

    def test_the_chain_of_two_links_resolves_end_to_end(self, account):
        """``partner.country_code`` es a su vez un ``related`` de
        ``country.code``: el recorrido atraviesa dos proyecciones seguidas, que
        es la forma que la fuente declara en ``:102``."""
        assert account.country_code == 'MX'

    def test_none_of_the_four_took_a_column(self):
        """El defecto ``store=False`` de ``:455``, medido donde importa: si
        alguno hubiera tomado columna, ``makemigrations`` propondría un
        ``AddField`` y la base divergiría del árbol."""
        declared = {
            ('ResBank', 'country_code'),
            ('ResPartnerBank', 'bank_name'),
            ('ResPartnerBank', 'bank_bic'),
            ('ResPartnerBank', 'country_code'),
        }
        for model_name, field_name in declared:
            columns = {f.name for f in
                       apps.get_model('base', model_name)._meta.get_fields()}
            assert field_name not in columns, (
                f'{model_name}.{field_name} tomó columna')
            assert isinstance(
                getattr(apps.get_model('base', model_name), field_name),
                NonStored)
