"""La mitad relacional de ``ir.fields.converter`` (#132).

≙ ``odoo19c: odoo/addons/base/models/ir_fields.py`` — ``for_model``,
``db_id_for``, ``_xmlid_to_record_id``, ``_referencing_subfield`` y los cuatro
conversores relacionales. Es la mitad que traduce una **referencia** (un
nombre visible, un identificador externo, un id de base) al registro al que
apunta; sin ella ``BaseModel.load`` sólo sabe importar escalares.

Qué haría fallar a estos casos
==============================

Una resolución que no resuelve devuelve ``None`` y el cargador la reporta como
error, así que un caso que sólo mirase «no reventó» sería verde con el
converter ausente. Cada caso de abajo **afirma el id concreto** del registro
que la referencia debía encontrar, o el tipo de error que la fuente promete
cuando no existe.
"""
import pytest

from addons.base.models.ir_fields import IrFieldsConverter, ImportWarning
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_country import ResCountry
from addons.base.models.res_partner import ResPartner
from orm.environments import context_scope
from service.db import Savepoint
from django.db import DEFAULT_DB_ALIAS, connections


@pytest.fixture
def savepoint(db):
    punto = Savepoint(connections[DEFAULT_DB_ALIAS])
    yield punto
    punto.close(rollback=False)


@pytest.fixture
def country(db):
    return ResCountry.objects.create(name='Sinelandia', code='ZY')


@pytest.mark.django_db
class TestTheReferencingSubfield:
    """≙ ``_referencing_subfield`` — cuál de las tres formas de referencia trae."""

    def test_it_returns_the_only_referencing_key(self):
        assert IrFieldsConverter._referencing_subfield({'id': 'base.zy'}) == ('id', [])

    def test_a_non_referencing_key_is_refused(self):
        with pytest.raises(ValueError):
            IrFieldsConverter._referencing_subfield({'name': 'Sinelandia'})

    def test_two_referencing_keys_are_ambiguous(self):
        with pytest.raises(ValueError):
            IrFieldsConverter._referencing_subfield({'id': 'base.zy', '.id': '1'})


@pytest.mark.django_db
class TestTheDatabaseIdSubfield:
    """``.id`` — el id de base, con su guarda de existencia."""

    def test_an_existing_database_id_resolves(self, country, savepoint):
        field = ResPartner._meta.get_field('country')

        resolved, warnings = IrFieldsConverter.db_id_for(
            ResPartner, field, '.id', str(country.pk), savepoint)

        assert resolved == country.pk
        assert warnings == []

    def test_a_missing_database_id_is_refused(self, savepoint):
        field = ResPartner._meta.get_field('country')

        with pytest.raises(ValueError):
            IrFieldsConverter.db_id_for(ResPartner, field, '.id', '99999999',
                                        savepoint)

    def test_a_non_numeric_database_id_is_refused(self, savepoint):
        field = ResPartner._meta.get_field('country')

        with pytest.raises(ValueError):
            IrFieldsConverter.db_id_for(ResPartner, field, '.id', 'no-soy-un-id',
                                        savepoint)


@pytest.mark.django_db
class TestTheExternalIdSubfield:
    """``id`` — el identificador externo, contra ``ir.model.data``."""

    def test_a_declared_external_id_resolves(self, country, savepoint):
        IrModelData.objects.create(module='base', name='country_zy',
                                   model='res.country', res_id=country.pk)
        field = ResPartner._meta.get_field('country')

        resolved, _warnings = IrFieldsConverter.db_id_for(
            ResPartner, field, 'id', 'base.country_zy', savepoint)

        assert resolved == country.pk

    def test_the_current_module_completes_a_bare_name(self, country, savepoint):
        """Sin punto, el módulo lo pone ``_import_current_module``."""
        IrModelData.objects.create(module='base', name='country_zy',
                                   model='res.country', res_id=country.pk)
        field = ResPartner._meta.get_field('country')

        with context_scope(_import_current_module='base'):
            resolved, _warnings = IrFieldsConverter.db_id_for(
                ResPartner, field, 'id', 'country_zy', savepoint)

        assert resolved == country.pk

    def test_an_external_id_of_another_model_is_refused(self, country, savepoint):
        """La guarda del modelo: un xmlid reusado no apunta a otra tabla."""
        IrModelData.objects.create(module='base', name='impostor',
                                   model='res.partner', res_id=country.pk)
        field = ResPartner._meta.get_field('country')

        with pytest.raises(ValueError):
            IrFieldsConverter.db_id_for(ResPartner, field, 'id',
                                        'base.impostor', savepoint)

    def test_an_unknown_external_id_is_refused(self, savepoint):
        field = ResPartner._meta.get_field('country')

        with pytest.raises(ValueError):
            IrFieldsConverter.db_id_for(ResPartner, field, 'id',
                                        'base.no_existe', savepoint)


@pytest.mark.django_db
class TestTheNameSubfield:
    """``None`` — la búsqueda por etiqueta visible, vía ``name_search``."""

    def test_a_visible_name_resolves(self, country, savepoint):
        field = ResPartner._meta.get_field('country')

        resolved, _warnings = IrFieldsConverter.db_id_for(
            ResPartner, field, None, 'Sinelandia', savepoint)

        assert resolved == country.pk

    def test_several_matches_warn_without_failing(self, country, savepoint):
        ResCountry.objects.create(name='Sinelandia', code='ZX')
        field = ResPartner._meta.get_field('country')

        _resolved, warnings = IrFieldsConverter.db_id_for(
            ResPartner, field, None, 'Sinelandia', savepoint)

        assert any(isinstance(w, ImportWarning) for w in warnings)

    def test_an_empty_name_is_the_empty_value(self, savepoint):
        field = ResPartner._meta.get_field('country')

        assert IrFieldsConverter.db_id_for(
            ResPartner, field, None, '', savepoint) == (False, [])


@pytest.mark.django_db
class TestTheManyToOneConverter:
    """≙ ``_str_to_many2one`` — desempaqueta el registro y delega."""

    def test_it_resolves_through_the_subfield(self, country, savepoint):
        field = ResPartner._meta.get_field('country')

        resolved, _warnings = IrFieldsConverter._str_to_many2one(
            ResPartner, field, [{None: 'Sinelandia'}], savepoint)

        assert resolved == country.pk


@pytest.mark.django_db
class TestForModel:
    """≙ ``for_model`` — el converter completo de un registro."""

    def test_it_converts_every_column_it_knows(self, savepoint):
        convert = IrFieldsConverter.for_model(ResPartner, savepoint=savepoint)
        errors = []

        converted = convert({'name': 'Ada', 'is_company': '1'},
                            lambda field, exc: errors.append((field, exc)))

        assert errors == []
        assert converted['name'] == 'Ada'
        assert converted['is_company'] is True

    def test_an_empty_cell_becomes_the_empty_value(self, savepoint):
        convert = IrFieldsConverter.for_model(ResPartner, savepoint=savepoint)

        converted = convert({'name': ''}, lambda field, exc: None)

        assert converted['name'] is False

    def test_a_referencing_key_is_not_converted(self, savepoint):
        """``id``/``.id``/``None`` los consume el cargador, no el converter."""
        convert = IrFieldsConverter.for_model(ResPartner, savepoint=savepoint)

        converted = convert({'id': 'base.ada', 'name': 'Ada'},
                            lambda field, exc: None)

        assert 'id' not in converted

    def test_a_bad_value_is_logged_not_raised(self, savepoint):
        convert = IrFieldsConverter.for_model(ResPartner, savepoint=savepoint)
        errors = []

        convert({'active': 'quizas'},
                lambda field, exc: errors.append((field, exc)))

        assert [field for field, _exc in errors] == ['active']
