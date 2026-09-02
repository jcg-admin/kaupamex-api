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
6. **Los diez despachadores** (tarea #129) — uno por cada tipo de la lista
   cerrada, con el control que delata si el alias de Django cambió.
"""
import pytest
from django.db import models

import fields
from addons.base.models import ResCompany, ResPartner
from orm.environments import company_scope, get_current_company
from orm.fields_company_dependent import (COMPANY_DEPENDENT_FIELDS,
                                          CompanyDependent, make_dispatcher)
from orm.fields_nonstored import NonStored
from orm.fields_textual import Html


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


class TestTenDispatchers:
    """Los diez tipos de la lista cerrada despachan — tarea #129.

    Hasta esta tarea sólo ``Char`` lo hacía; los otros nueve eran alias pelados
    de Django y ``fields.Integer(company_dependent=True)`` moría con un
    ``TypeError`` del constructor de Django. La lista de tipos es de la fuente
    (``odoo19c: odoo/orm/fields.py:42-44``), así que el despachador va en los
    diez y no en los que hoy tienen consumidor.
    """

    #: ``(nombre en fields, base_type, clase de Django sin la palabra clave)``.
    DISPATCHERS = [
        ('Char', 'char', models.CharField),
        ('Text', 'text', models.TextField),
        ('Html', 'html', models.TextField),
        ('Integer', 'integer', models.IntegerField),
        ('Float', 'float', models.FloatField),
        ('Boolean', 'boolean', models.BooleanField),
        ('Date', 'date', models.DateField),
        ('Datetime', 'datetime', models.DateTimeField),
        ('Selection', 'selection', models.CharField),
    ]

    @pytest.mark.parametrize('name,base_type,_plain', DISPATCHERS)
    def test_the_keyword_returns_a_company_dependent(self, name, base_type,
                                                     _plain):
        field = getattr(fields, name)(company_dependent=True)
        assert isinstance(field, CompanyDependent)

    @pytest.mark.parametrize('name,base_type,_plain', DISPATCHERS)
    def test_the_base_type_is_the_one_of_the_declared_field(self, name,
                                                            base_type, _plain):
        assert getattr(fields, name)(
            company_dependent=True).base_type == base_type

    @pytest.mark.parametrize('name,_base_type,plain', DISPATCHERS)
    def test_without_the_keyword_the_field_is_the_django_one_of_before(
            self, name, _base_type, plain):
        # CONTROL que puede fallar: es el que delata que el despachador cambió
        # el alias. Sin él, envolver ``Integer`` en una función y devolver otra
        # cosa pasaría inadvertido hasta la primera migración.
        field = getattr(fields, name)()
        assert type(field) is plain or isinstance(field, plain)

    def test_the_ten_cover_the_closed_list_of_the_reference(self):
        cubiertos = {b for _n, b, _p in self.DISPATCHERS}
        cubiertos.add('many2one')                  # rama propia, ver abajo
        assert cubiertos == set(COMPANY_DEPENDENT_FIELDS)

    def test_html_keeps_its_type_identity(self):
        # H-API-700: ``tools/convert.py`` hace ``isinstance(field_obj, Html)``, así
        # que ``Html`` no puede ser una función. Su rama va en ``__new__``.
        assert isinstance(fields.Html(), Html)

    def test_a_company_dependent_html_is_no_longer_an_html_instance(self):
        # Y no debe serlo: la columna ya no es ``TEXT`` sino ``jsonb``.
        assert not isinstance(fields.Html(company_dependent=True), Html)

    def test_the_factory_rejects_a_type_outside_the_closed_list(self):
        with pytest.raises(ValueError, match='no es uno de'):
            make_dispatcher('Binary', 'binary', models.BinaryField)

    def test_the_dispatcher_keeps_its_public_name(self):
        # El ``repr`` y el traceback dicen ``Integer``, no ``dispatcher``.
        assert fields.Integer.__name__ == 'Integer'


class TestMany2oneDispatcher:
    """``Many2one`` tiene rama propia: el comodelo hay que guardarlo."""

    def test_the_keyword_returns_a_company_dependent(self):
        field = fields.Many2one('base.ResPartner', company_dependent=True)
        assert isinstance(field, CompanyDependent)
        assert field.base_type == 'many2one'

    def test_the_comodel_is_kept_from_a_string(self):
        field = fields.Many2one('base.ResPartner', company_dependent=True)
        assert field.company_dependent_comodel == 'base.ResPartner'

    def test_the_comodel_is_kept_from_a_class(self):
        field = fields.Many2one(ResPartner, company_dependent=True)
        assert field.company_dependent_comodel == 'base.ResPartner'

    def test_without_a_target_it_refuses(self):
        # Sin FK real el comodelo es lo único que queda para indexarlo; sin él
        # ``many2one_company_dependents`` no puede responder.
        with pytest.raises(ValueError, match='modelo \\ndestino|modelo destino'):
            fields.Many2one(company_dependent=True)

    def test_the_foreign_key_only_arguments_are_dropped(self):
        # ``on_delete`` no tiene destinatario: el jsonb no deja FK que
        # cascadear. Se descarta declarado, no en silencio.
        field = fields.Many2one(
            'base.ResPartner', on_delete=models.CASCADE,
            related_name='irrelevante', company_dependent=True)
        assert isinstance(field, CompanyDependent)

    def test_the_positional_on_delete_is_dropped_too(self):
        field = fields.Many2one(
            'base.ResPartner', models.CASCADE, company_dependent=True)
        assert isinstance(field, CompanyDependent)
        assert field.company_dependent_comodel == 'base.ResPartner'

    def test_store_false_and_company_dependent_are_exclusive(self):
        with pytest.raises(ValueError, match='excluyentes'):
            fields.Many2one(
                'base.ResPartner', store=False, company_dependent=True)

    def test_without_the_keyword_it_is_still_a_foreign_key(self):
        field = fields.Many2one(
            'base.ResPartner', on_delete=models.CASCADE)
        assert isinstance(field, models.ForeignKey)


class TestABareStoreFalseGivesANonStoredField:
    """El despachador de :func:`make_dispatcher` sin ``related=``.

    La rama miraba ``related and not store``, así que un ``store=False``
    declarado a secas —la forma con que la referencia escribe un ``compute``
    sin columna, ``fields.Integer(compute='_compute_…')``— salía como columna
    de Django y aparecía en ``makemigrations``. Primer consumidor:
    ``hr_recruitment/models/digest.py`` (tarea #159).
    """

    def test_integer_without_store_is_the_plain_django_field(self):
        assert isinstance(fields.Integer(), models.IntegerField)

    def test_integer_with_store_false_is_non_stored(self):
        assert isinstance(fields.Integer(store=False), NonStored)

    def test_float_with_store_false_is_non_stored(self):
        assert isinstance(fields.Float(store=False), NonStored)

    def test_store_true_keeps_the_column(self):
        """Discriminante: si la rama leyera cualquier ``store`` presente en
        vez de su valor, un ``store=True`` explícito también perdería la
        columna."""
        assert isinstance(fields.Integer(store=True), models.IntegerField)
