"""``orm/fields_properties.py`` — el tramo de lectura, validación y búsqueda.

Tarea **#130**. Cierra el porte de ``odoo19c: odoo/orm/fields_properties.py``
(1063 líneas): las tres clases con sus **38 símbolos**, medido por AST contra
la referencia con un solo alias declarado (``condition_to_sql`` →
``condition_to_q``, la divergencia de forma que ``orm/domains.py`` ya declara
para toda esa capa).

Cinco bloques, y el segundo es el que un porte silencioso perdería:

1. **Los símbolos existen** con su nombre y su firma.
2. **La validación rechaza**, que es lo que el alias ``= models.JSONField`` no
   hacía: hasta este porte una definición con clave inventada, tipo
   desconocido o nombre duplicado entraba a la columna.
3. **La tríada de definición resuelve** en las cuatro declaraciones del árbol.
4. **La lectura es honesta** — una opción retirada del contenedor sale
   ``False``, no como un valor huérfano.
5. **La búsqueda por propiedad compila**, con la contención ``jsonb`` que el
   compilador genérico no da.
"""
import pytest
from django.apps import apps
from django.db.models import Q

from addons.fleet.models.fleet_vehicle import FleetVehicle
from addons.fleet.models.fleet_vehicle_model import FleetVehicleModel
from addons.fleet.models.fleet_vehicle_model_brand import (
    FleetVehicleModelBrand)
from orm.domains import to_q
from orm.fields_properties import (Properties, PropertiesDefinition, Property,
                                   check_property_field_value_name)


def _field():
    return FleetVehicle._meta.get_field('vehicle_properties')


def _definition_field():
    return FleetVehicleModel._meta.get_field('vehicle_properties_definition')


#: Los 26 métodos que la referencia declara en ``Properties``, con el único
#: alias del porte. Se enumeran para que un símbolo que desaparezca lo diga.
PORTED_PROPERTIES = [
    '_setup_attrs__', '_setup_definition_attrs', 'setup', 'setup_related',
    '_compute', '_add_default_values', '_get_properties_definition',
    'convert_to_column', 'convert_to_cache', 'convert_to_record',
    'convert_to_read', 'convert_to_read_multi', 'convert_to_write',
    'convert_to_export', '_get_res_ids_per_model', '_add_display_name',
    '_remove_display_name', '_add_missing_names', '_parse_json_types',
    '_list_to_dict', '_dict_to_list', 'write', 'property_to_sql',
    'expression_getter', 'filter_function', 'condition_to_q',
]

PORTED_DEFINITION = [
    'convert_to_column', 'convert_to_cache', 'convert_to_record',
    'convert_to_read', 'convert_to_write', '_validate_properties_definition',
]


class TestPortedSurface:
    """Los símbolos están, y con el guion bajo que la fuente les puso."""

    def test_the_properties_methods_are_installed(self):
        missing = [n for n in PORTED_PROPERTIES if not hasattr(Properties, n)]
        assert missing == []

    def test_the_definition_methods_are_installed(self):
        missing = [n for n in PORTED_DEFINITION
                   if not hasattr(PropertiesDefinition, n)]
        assert missing == []

    def test_the_underscore_prefix_is_preserved(self):
        # H-API-581: quitar el guion bajo publica lo que la fuente reservó.
        private = [n for n in PORTED_PROPERTIES if n.startswith('_')]
        assert len(private) == 12
        for name in private:
            assert not hasattr(Properties, name.lstrip('_')), (
                'existe la forma pública de %s' % name)

    def test_the_definition_is_no_longer_an_alias(self):
        # Hasta este porte era ``PropertiesDefinition = models.JSONField``.
        assert PropertiesDefinition is not Properties
        assert issubclass(PropertiesDefinition, __import__(
            'django.db.models', fromlist=['JSONField']).JSONField)
        assert PropertiesDefinition.properties_fields == ()

    def test_the_column_path_does_not_move(self):
        # Las migraciones generadas cuando esto era un alias siguen valiendo.
        for field in (_field(), _definition_field()):
            assert field.deconstruct()[1] == 'django.db.models.JSONField'


class TestDefinitionWiring:
    """``definition='campo.definicion'`` resuelve en las cuatro del árbol."""

    def test_the_triad_is_split(self):
        field = _field()
        assert field.definition == 'model.vehicle_properties_definition'
        assert field.definition_record == 'model'
        assert field.definition_record_field == 'vehicle_properties_definition'

    def test_every_declaration_resolves_end_to_end(self):
        """Toda declaración con ``definition=`` resuelve a un campo existente.

        El conteo **se deriva, no se transcribe**: era ``== 4``, y al portar
        ``CrmLead.lead_properties`` pasó a 5 — la cifra es propiedad de un
        árbol que crece, así que fijarla convierte cada declaración nueva en un
        rojo espurio (``calibration-verified-numbers.md``, corolario de la
        cifra que vive en código).

        Lo que sí se afirma es que hubo **al menos una**: sin esa cota, un
        recorrido roto —que no encuentre ningún ``Properties``— publicaría un
        verde que no distingue *"todas resuelven"* de *"no miré ninguna"*, que
        es el sub-patrón D de ``metrica-decide-la-conclusion.md``.
        """
        resueltas = []
        for model in apps.get_models():
            for field in model._meta.get_fields():
                if not isinstance(field, Properties) or not field.definition:
                    continue
                container = model._meta.get_field(field.definition_record)
                # el campo de definición existe en el contenedor
                container.related_model._meta.get_field(
                    field.definition_record_field)
                resueltas.append(f'{model._meta.label}.{field.name}')
        assert resueltas, (
            'ninguna declaración con definition= fue medida: el recorrido no '
            've los campos Properties, y su cero no es evidencia')

    def test_a_malformed_definition_is_rejected(self):
        with pytest.raises(AssertionError):
            Properties(definition='sin_punto')._setup_definition_attrs()


class TestDefinitionValidation:
    """Lo que el alias NO hacía: rechazar una definición mal formada.

    Medido con la **guarda anulada** (sub-patrón D de
    ``metrica-decide-la-conclusion.md``): sustituyendo el cuerpo de
    ``_validate_properties_definition`` por un ``return``, el archivo pasa de
    **34 passed** a **8 failed, 26 passed** — caen los ocho casos negativos de
    esta clase y ni uno más. El positivo sobrevive, y también
    ``test_the_property_name_is_bounded``, que mide otra guarda
    (``check_property_field_value_name``, llamada aparte). Restaurado y
    verificado con ``git diff`` sobre el archivo.

    Sin ese control, un verde aquí no distinguiría «la validación rechaza» de
    «el caso no llegaba a la validación».
    """

    @pytest.fixture
    def container(self, db):
        brand = FleetVehicleModelBrand.objects.create(name='Probe Brand')
        return FleetVehicleModel.objects.create(name='Probe', brand=brand)

    def _validate(self, definition, container):
        _definition_field()._validate_properties_definition(
            definition, container)

    def test_a_well_formed_definition_passes(self, container):
        self._validate([{'name': 'color', 'type': 'char', 'string': 'Color'}],
                       container)

    def test_an_unknown_key_is_rejected(self, container):
        with pytest.raises(ValueError, match='not allowed'):
            self._validate([{'name': 'color', 'type': 'char',
                             'inventada': 1}], container)

    def test_a_missing_required_key_is_rejected(self, container):
        with pytest.raises(ValueError, match='missing'):
            self._validate([{'name': 'color'}], container)

    def test_an_unknown_type_is_rejected(self, container):
        with pytest.raises(ValueError, match='Wrong property type'):
            self._validate([{'name': 'color', 'type': 'inventado'}], container)

    def test_a_duplicated_name_is_rejected(self, container):
        with pytest.raises(ValueError, match='duplicated'):
            self._validate([{'name': 'color', 'type': 'char'},
                            {'name': 'color', 'type': 'char'}], container)

    def test_html_needs_the_suffix_and_the_suffix_needs_html(self, container):
        with pytest.raises(ValueError, match='should end with'):
            self._validate([{'name': 'nota', 'type': 'html'}], container)
        with pytest.raises(ValueError, match='Only HTML'):
            self._validate([{'name': 'nota_html', 'type': 'char'}], container)

    def test_a_parameter_outside_its_types_is_rejected(self, container):
        # ``comodel`` sólo vale para many2one / many2many.
        with pytest.raises(ValueError, match='Invalid property parameter'):
            self._validate([{'name': 'color', 'type': 'char',
                             'comodel': 'fleet.FleetVehicle'}], container)

    def test_an_unknown_comodel_is_rejected(self, container):
        with pytest.raises(ValueError, match='Invalid model name'):
            self._validate([{'name': 'v', 'type': 'many2one',
                             'comodel': 'no.existe'}], container)

    def test_duplicated_options_are_rejected(self, container):
        with pytest.raises(ValueError, match='options are duplicated'):
            self._validate([{'name': 's', 'type': 'selection',
                             'selection': [['a', 'A'], ['a', 'B']]}], container)

    def test_the_property_name_is_bounded(self):
        # Va interpolado en el SQL: sólo minúsculas, dígitos y guion bajo.
        check_property_field_value_name('color_1')
        for bad in ('', 'Color', 'a b', 'x' * 513):
            with pytest.raises(ValueError):
                check_property_field_value_name(bad)


class TestReadIsHonest:
    """La lectura no devuelve un valor que el contenedor ya no define."""

    def test_a_retired_selection_option_reads_false(self):
        values = [{'name': 's', 'type': 'selection',
                   'selection': [['a', 'A']], 'value': 'b'}]
        Properties._parse_json_types(values, {})
        assert values[0]['value'] is False

    def test_a_tag_outside_the_container_is_dropped(self):
        values = [{'name': 't', 'type': 'tags',
                   'tags': [['a', 'A', 1]], 'value': ['a', 'z']}]
        Properties._parse_json_types(values, {})
        assert values[0]['value'] == ['a']

    def test_a_many2one_to_a_missing_row_reads_false(self):
        values = [{'name': 'v', 'type': 'many2one',
                   'comodel': 'fleet.FleetVehicle', 'value': 999999}]
        Properties._parse_json_types(values, {'fleet.FleetVehicle': set()})
        assert values[0]['value'] is False

    def test_a_many2many_drops_duplicates_and_preserves_order(self):
        values = [{'name': 'v', 'type': 'many2many',
                   'comodel': 'fleet.FleetVehicle', 'value': [2, 1, 2]}]
        Properties._parse_json_types(
            values, {'fleet.FleetVehicle': {1, 2}})
        assert values[0]['value'] == [2, 1]

    def test_an_html_property_without_the_suffix_reads_false(self):
        values = [{'name': 'nota', 'type': 'html', 'value': '<b>x</b>'}]
        Properties._parse_json_types(values, {})
        assert values[0]['value'] is False

    def test_an_unknown_type_raises(self):
        with pytest.raises(ValueError, match='Wrong property type'):
            Properties._parse_json_types(
                [{'name': 'x', 'type': 'inventado', 'value': 1}], {})

    def test_the_record_format_is_a_mapping(self):
        prop = _field().convert_to_record({'color': 'red'}, None)
        assert isinstance(prop, Property)
        assert len(prop) == 1
        # sin registro el acceso devuelve False, como la fuente
        assert prop['color'] is False

    def test_the_export_format_unwraps_the_property(self):
        field = _field()
        prop = field.convert_to_record({'color': 'red'}, None)
        assert field.convert_to_export(prop, None) == {'color': 'red'}
        assert field.convert_to_export(None, None) == ''


@pytest.mark.django_db
class TestComputeOnSave:
    """El ``compute`` de la fuente, con ``pre_save`` como receptor."""

    @pytest.fixture
    def brand(self):
        return FleetVehicleModelBrand.objects.create(name='Marca')

    def test_a_value_survives_when_the_container_declares_it(self, brand):
        model = FleetVehicleModel.objects.create(
            name='Con esquema', brand=brand,
            vehicle_properties_definition=[
                {'name': 'color', 'type': 'char', 'string': 'Color'}])
        row = FleetVehicle.objects.create(
            model=model, vehicle_properties={'color': 'azul'})
        row.refresh_from_db()
        assert row.vehicle_properties == {'color': 'azul'}

    def test_the_container_default_fills_an_absent_value(self, brand):
        model = FleetVehicleModel.objects.create(
            name='Con default', brand=brand,
            vehicle_properties_definition=[
                {'name': 'color', 'type': 'char', 'default': 'rojo'}])
        row = FleetVehicle.objects.create(model=model)
        row.refresh_from_db()
        assert row.vehicle_properties == {'color': 'rojo'}

    def test_a_value_without_a_definition_is_blanked(self, brand):
        """Es la conducta de la fuente, y sorprende: se porta igual.

        ``_add_default_values`` devuelve ``{}`` cuando el contenedor no declara
        esquema (``odoo19c: :393-396``), y el compute lo escribe. Una propiedad
        que el contenedor no define no significa nada, así que no se guarda.
        """
        model = FleetVehicleModel.objects.create(name='Sin esquema', brand=brand)
        row = FleetVehicle.objects.create(
            model=model, vehicle_properties={'color': 'azul'})
        row.refresh_from_db()
        assert not row.vehicle_properties

    def test_a_value_outside_the_definition_is_dropped(self, brand):
        # `_dict_to_list` ignora lo que el contenedor no declara.
        model = FleetVehicleModel.objects.create(
            name='Parcial', brand=brand,
            vehicle_properties_definition=[{'name': 'color', 'type': 'char'}])
        row = FleetVehicle.objects.create(
            model=model, vehicle_properties={'color': 'azul', 'sobra': 1})
        row.refresh_from_db()
        assert row.vehicle_properties == {'color': 'azul'}


class TestSearchByProperty:
    """La ruta con punto compila, y con la contención que la fuente exige."""

    def _where(self, domain):
        query = str(FleetVehicle.objects.filter(
            to_q(domain, FleetVehicle)).query)
        return query[query.find('WHERE'):query.find('ORDER')]

    def test_equality_also_checks_the_list_subset(self):
        # «left can be an array or a single value! Even if we use the '='
        # operator, we must check the list subset» — odoo19c: :713-716.
        where = self._where([('vehicle_properties.color', '=', 'red')])
        assert '-> color) = ' in where
        assert '@>' in where, 'falta la contención jsonb'

    def test_several_values_use_contained_by(self):
        where = self._where([('vehicle_properties.tags', 'in', [1, 2])])
        assert '<@' in where

    def test_a_text_operator_uses_the_text_arrow(self):
        # ``->`` devuelve JSON con sus comillas; el texto necesita ``->>``.
        where = self._where([('vehicle_properties.name', 'ilike', 'bob')])
        assert '->> name' in where

    def test_a_comparison_keeps_the_json_arrow(self):
        where = self._where([('vehicle_properties.n', '>', 3)])
        assert '-> n) > ' in where

    def test_the_generic_compiler_would_miss_the_containment(self):
        """El control que hace medible lo que este símbolo aporta.

        Sin ``Properties.condition_to_q`` la condición la compila el camino
        genérico, que emite sólo la igualdad. Se construye aquí el ``Q`` que
        aquél produciría y se comprueba que **no** trae la contención: es la
        diferencia que el porte cierra, no una preferencia de forma.
        """
        generic = str(FleetVehicle.objects.filter(
            Q(vehicle_properties__color='red')).query)
        assert '@>' not in generic
        assert '@>' in self._where([('vehicle_properties.color', '=', 'red')])

    def test_an_invalid_operator_is_named(self):
        with pytest.raises(ValueError, match='Invalid operator'):
            _field().condition_to_q('vehicle_properties.color', '=?', 'x')

    def test_a_path_without_property_name_is_rejected(self):
        with pytest.raises(ValueError, match='Missing property name'):
            _field().condition_to_q('vehicle_properties', 'in', ['x'])


class TestBlockedSurface:
    """Lo bloqueado lo dice, y nombra su mecanismo."""

    def test_filter_function_names_its_blocker(self):
        with pytest.raises(NotImplementedError) as excinfo:
            _field().filter_function(None, 'vehicle_properties.c', '=', 'x')
        assert 'filtered_domain' in str(excinfo.value)
        assert '#373' in str(excinfo.value)
