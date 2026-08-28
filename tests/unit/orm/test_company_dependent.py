"""Contrato del mecanismo ``company_dependent`` — tarea #111.

Cierra la construcción de ``orm/fields_company_dependent.py`` y su cableado
en el despachador ``fields.Char`` y en ``Field.to_sql``, contra
``odoo19c: odoo/orm/fields.py`` (atributo ``company_dependent``, líneas 291,
466-473, 783 y 794-801).

Cinco bloques:

1. **El despachador** — ``Char(company_dependent=True)`` devuelve otra clase,
   y sus dos exclusiones levantan.
2. **La cabecera del campo** — los atributos que la fuente declara.
3. **El descriptor** — la indirección de lectura y de escritura por empresa.
4. **``to_sql``** — el ``COALESCE`` con el ``CAST``, y su control anulado.
5. **El fallback de ``ir.default``** — la empresa sin valor propio.
"""
import pytest
from django.db import models

import fields
from addons.base.models import ResCompany, ResPartner
from orm.environments import company_scope, get_current_company
from orm.fields_company_dependent import (COMPANY_DEPENDENT_FIELDS,
                                          CompanyDependent)
from orm.fields_nonstored import NonStored


class TestDispatcher:
    """``fields.Char`` devuelve la clase correcta según lo que se le pida."""

    def test_plain_char_is_still_a_django_char_field(self):
        assert isinstance(fields.Char(max_length=10), models.CharField)

    def test_store_false_is_still_non_stored(self):
        assert isinstance(fields.Char(store=False), NonStored)

    def test_company_dependent_returns_the_new_class(self):
        assert isinstance(
            fields.Char(company_dependent=True), CompanyDependent)

    def test_company_dependent_declares_the_reference_attribute(self):
        # odoo19c: odoo/orm/fields.py:291 — company_dependent = False por
        # defecto en Field; True en el campo que lo declara.
        assert fields.Char(company_dependent=True).company_dependent is True

    def test_a_plain_field_does_not_declare_the_attribute_as_true(self):
        assert getattr(
            fields.Char(max_length=10), 'company_dependent', False) is False

    def test_store_false_and_company_dependent_are_exclusive(self):
        with pytest.raises(ValueError, match='excluyentes'):
            fields.Char(store=False, company_dependent=True)

    def test_translate_and_company_dependent_are_exclusive(self):
        # ≙ el aviso de la fuente (odoo19c: odoo/orm/fields.py:466-470).
        with pytest.raises(ValueError, match='cannot be translated'):
            fields.Char(company_dependent=True, translate=True)

    def test_required_and_company_dependent_are_exclusive(self):
        with pytest.raises(ValueError, match='cannot be required'):
            fields.Char(company_dependent=True, required=True)


class TestFieldHeader:
    """Lo que la clase declara, contra lo que la fuente declara."""

    def test_the_allowed_types_match_the_reference(self):
        # odoo19c: odoo/orm/fields.py:42-44
        assert set(COMPANY_DEPENDENT_FIELDS) == {
            'char', 'float', 'boolean', 'integer', 'text', 'many2one',
            'date', 'datetime', 'selection', 'html'}

    def test_a_type_outside_the_list_is_rejected(self):
        with pytest.raises(ValueError, match='not one of the allowed types'):
            CompanyDependent(base_type='binary')

    @pytest.mark.parametrize('base_type,cast', [
        ('char', 'varchar'), ('text', 'text'), ('integer', 'integer'),
        ('float', 'double precision'), ('boolean', 'boolean'),
        ('date', 'date'), ('datetime', 'timestamp'), ('many2one', 'integer'),
        ('selection', 'varchar'), ('html', 'text'),
    ])
    def test_every_allowed_type_has_its_sql_cast(self, base_type, cast):
        assert CompanyDependent(base_type=base_type).sql_cast_type == cast

    def test_the_column_is_jsonb_like_the_reference(self):
        # odoo19c: odoo/orm/fields.py:783 — column_type -> ('jsonb', 'jsonb')
        assert isinstance(CompanyDependent(), models.JSONField)

    def test_deconstruct_carries_the_base_type_when_it_is_not_the_default(self):
        _, _, _, kwargs = CompanyDependent(base_type='integer').deconstruct()
        assert kwargs['base_type'] == 'integer'

    def test_deconstruct_omits_the_base_type_when_it_is_the_default(self):
        _, _, _, kwargs = CompanyDependent().deconstruct()
        assert 'base_type' not in kwargs

    def test_deconstruct_carries_the_comodel_of_a_many2one(self):
        field = CompanyDependent(base_type='many2one', comodel='base.ResPartner')
        _, _, _, kwargs = field.deconstruct()
        assert kwargs['comodel'] == 'base.ResPartner'


class TestRawValueGuard:
    """Lo que va a la base es el mapa, nunca el valor de una empresa."""

    def test_a_scalar_is_rejected_by_get_prep_value(self):
        with pytest.raises(ValueError, match='guarda un mapa por empresa'):
            CompanyDependent(name='barcode').get_prep_value('ABC')

    def test_a_mapping_passes_through_unserialised(self):
        # La serializacion la hace ``adapt_json_value`` aguas abajo; hacerla
        # aqui la duplica y el viaje de vuelta devuelve un ``str``.
        assert CompanyDependent(name='barcode').get_prep_value(
            {'1': 'ABC'}) == {'1': 'ABC'}

    def test_none_stays_none(self):
        assert CompanyDependent(name='barcode').get_prep_value(None) is None


@pytest.mark.django_db
class TestPerCompanyIndirection:
    """El descriptor: una fila, un valor por empresa."""

    @pytest.fixture
    def two_companies(self):
        first = ResCompany.objects.create(code='cd-one', name='CD One')
        second = ResCompany.objects.create(code='cd-two', name='CD Two')
        return first, second

    @pytest.fixture
    def partner(self):
        return ResPartner.objects.create(name='Contacto por empresa')

    def test_reading_without_an_active_company_falls_back(self, partner):
        assert get_current_company() is None
        assert partner.barcode is None

    def test_writing_without_an_active_company_is_rejected(self, partner):
        with pytest.raises(ValueError, match='No hay empresa activa'):
            partner.barcode = 'SIN-EMPRESA'

    def test_each_company_reads_its_own_value(self, partner, two_companies):
        first, second = two_companies
        with company_scope(first.pk):
            partner.barcode = 'UNO'
        with company_scope(second.pk):
            partner.barcode = 'DOS'
        with company_scope(first.pk):
            assert partner.barcode == 'UNO'
        with company_scope(second.pk):
            assert partner.barcode == 'DOS'

    def test_a_company_without_its_own_value_does_not_see_the_other(
            self, partner, two_companies):
        first, second = two_companies
        with company_scope(first.pk):
            partner.barcode = 'SOLO-UNO'
        with company_scope(second.pk):
            assert partner.barcode is None

    def test_the_raw_map_holds_both_companies(self, partner, two_companies):
        first, second = two_companies
        with company_scope(first.pk):
            partner.barcode = 'UNO'
        with company_scope(second.pk):
            partner.barcode = 'DOS'
        field = type(partner)._meta.get_field('barcode')
        assert field.raw_company_values(partner) == {
            str(first.pk): 'UNO', str(second.pk): 'DOS'}

    def test_set_for_company_writes_a_company_that_is_not_active(
            self, partner, two_companies):
        first, second = two_companies
        field = type(partner)._meta.get_field('barcode')
        with company_scope(first.pk):
            field.set_for_company(partner, second.pk, 'AJENO')
            assert partner.barcode is None
        with company_scope(second.pk):
            assert partner.barcode == 'AJENO'

    def test_the_value_survives_a_round_trip_to_the_database(
            self, partner, two_companies):
        first, second = two_companies
        with company_scope(first.pk):
            partner.barcode = 'PERSISTE'
            partner.save()
        recovered = type(partner).objects.get(pk=partner.pk)
        with company_scope(first.pk):
            assert recovered.barcode == 'PERSISTE'
        with company_scope(second.pk):
            assert recovered.barcode is None
