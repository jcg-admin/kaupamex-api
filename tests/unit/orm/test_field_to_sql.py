"""Contrato de ``orm.models.FieldSqlMixin`` — tarea #127.

Porta ``BaseModel._field_to_sql`` (``odoo19c: odoo/orm/models.py:2910``) y sus
tres dependencias —``_traverse_related_sql`` (``:2889``),
``_check_field_access`` (``:3384``) y ``_has_field_access`` (``:3370``)— más el
par ``Field.to_sql``/``Field.property_to_sql`` de ``orm/fields.py`` y
``Many2one.join`` de ``orm/fields_relational.py``.

El sujeto es ``PropertiesBaseDefinition``, primer adoptante del mixin: tiene
las dos formas que el mecanismo resuelve, una FK real y un campo JSON.
"""
import pytest
from django.db import models as django_models

from addons.base.models import PropertiesBaseDefinition
from addons.base.models.ir_model import IrModel, IrModelFields
from exceptions import AccessError
from orm.models import NO_ACCESS, FieldSqlMixin
from tools.query import Query
from tools.sql import SQL

TABLE = PropertiesBaseDefinition._meta.db_table


@pytest.fixture
def definition():
    """Una instancia sin guardar basta: ``_field_to_sql`` compone SQL, no lo corre."""
    return PropertiesBaseDefinition()


class TestPortedSurface:
    """Los símbolos, con el nombre y el sitio de la fuente."""

    @pytest.mark.parametrize('name', [
        '_field_to_sql', '_traverse_related_sql',
        '_check_field_access', '_has_field_access', '_fields',
    ])
    def test_the_reference_method_is_declared_on_the_mixin(self, name):
        assert hasattr(FieldSqlMixin, name)

    def test_the_field_base_carries_the_two_sql_generation_methods(self):
        # odoo19c: odoo/orm/fields.py:1209 y :1241 — cuelgan de `Field`, así
        # que TODO campo los tiene. Aquí la clase base es la de Django.
        assert hasattr(django_models.Field, 'to_sql')
        assert hasattr(django_models.Field, 'property_to_sql')

    def test_the_json_field_overrides_property_to_sql(self):
        # odoo19c: fields_properties.py:674 — sólo quien contiene sub-campos
        # sabe extraer uno.
        assert (django_models.JSONField.property_to_sql
                is not django_models.Field.property_to_sql)

    def test_the_foreign_key_carries_join(self):
        # odoo19c: fields_relational.py:466 — el salto de un camino relacional.
        assert hasattr(django_models.ForeignKey, 'join')


class TestFieldsRegistry:
    """``_fields`` — el registro por nombre, ≙ ``BaseModel._fields``."""

    def test_it_maps_concrete_field_names(self, definition):
        assert set(definition._fields) == {
            'id', 'created_at', 'updated_at',
            'properties_field', 'properties_definition',
        }

    def test_the_values_are_the_django_fields(self, definition):
        assert isinstance(definition._fields['properties_field'],
                          django_models.ForeignKey)


class TestFieldToSql:
    """La conversión, contra la forma de la fuente."""

    def test_a_plain_column_is_quoted_with_its_alias(self, definition):
        assert definition._field_to_sql(TABLE, 'properties_definition').code == \
            '"properties_base_definition"."properties_definition"'

    def test_a_foreign_key_uses_its_COLUMN_not_its_field_name(self, definition):
        # La fuente entrecomilla `self.name` porque allá el nombre del campo ES
        # el de la columna. Aquí una FK las separa: el campo es
        # `properties_field` y la columna `properties_field_id`. Lo que va en
        # SQL es la columna — si esto dijera `properties_field`, PostgreSQL
        # rechazaría la sentencia.
        assert definition._field_to_sql(TABLE, 'properties_field').code == \
            '"properties_base_definition"."properties_field_id"'

    def test_an_unknown_field_is_refused_with_the_reference_message(self, definition):
        with pytest.raises(ValueError, match="Invalid field 'no_existe'"):
            definition._field_to_sql(TABLE, 'no_existe')

    def test_the_alias_is_honoured_not_the_table(self, definition):
        assert definition._field_to_sql('otro_alias', 'properties_definition').code == \
            '"otro_alias"."properties_definition"'


class TestPropertyExpression:
    """``campo.propiedad`` — el segundo tramo, vía ``property_to_sql``."""

    def test_a_property_becomes_the_json_arrow_operator(self, definition):
        sql = definition._field_to_sql(TABLE, 'properties_definition.color')
        assert sql.code == \
            '("properties_base_definition"."properties_definition" -> %s)'

    def test_the_property_name_travels_as_a_parameter_not_interpolated(self, definition):
        # Es lo que impide que el nombre entre en el SQL como texto. Si se
        # interpolara, `check_property_field_value_name` sería la única
        # defensa; así hay dos.
        sql = definition._field_to_sql(TABLE, 'properties_definition.color')
        assert sql.params == ['color']

    @pytest.mark.parametrize('bad', ['MAL', 'con-guion', 'con espacio',
                                     'punto.punto', 'x' * 513])
    def test_a_malformed_property_name_is_refused(self, definition, bad):
        with pytest.raises(ValueError, match='Wrong property field value name'):
            definition._field_to_sql(TABLE, f'properties_definition.{bad}')

    def test_an_empty_property_name_is_not_a_property_expression(self, definition):
        # `parse_field_expr('campo.')` devuelve ('campo', ''), y `if
        # property_name:` descarta la cadena vacía — así que no llega a
        # `property_to_sql` y no hay nada que validar. Es la conducta de la
        # fuente, no una laxitud de este puerto.
        assert definition._field_to_sql(TABLE, 'properties_definition.').code == \
            '"properties_base_definition"."properties_definition"'

    def test_a_property_on_a_field_that_has_none_is_refused(self, definition):
        # El caso base de `Field.property_to_sql`: sólo un campo con
        # sub-campos sabe extraer uno.
        with pytest.raises(ValueError, match='Invalid field property'):
            definition._field_to_sql(TABLE, 'created_at.algo')


class TestFieldAccess:
    """``_has_field_access`` / ``_check_field_access`` — ≙ ``:3370`` y ``:3384``."""

    def test_a_field_without_groups_is_accessible(self, definition):
        assert definition._has_field_access(
            definition._fields['properties_definition'], 'read') is True

    def test_no_access_forbids_the_field(self, definition):
        field = definition._fields['properties_definition']
        field.groups = NO_ACCESS
        try:
            assert definition._has_field_access(field, 'read') is False
            with pytest.raises(AccessError, match='properties_definition'):
                definition._field_to_sql(TABLE, 'properties_definition')
        finally:
            del field.groups

    def test_the_error_names_the_operation(self, definition):
        field = definition._fields['properties_definition']
        field.groups = NO_ACCESS
        try:
            with pytest.raises(AccessError, match='read'):
                definition._check_field_access(field, 'read')
        finally:
            del field.groups

    def test_the_check_runs_before_the_conversion(self, definition):
        # El orden de la fuente: `_check_field_access` está ANTES de
        # `field.to_sql`. Si se invirtiera, un campo prohibido igual emitiría
        # su columna cuando la conversión no fallara — y el rechazo llegaría
        # tarde o no llegaría.
        field = definition._fields['properties_definition']
        field.groups = NO_ACCESS
        try:
            with pytest.raises(AccessError):
                definition._field_to_sql(TABLE, 'properties_definition.color')
        finally:
            del field.groups


class TestToSqlRefusesWhatHasNoColumn:
    """``to_sql`` rechaza lo no almacenado, con el mensaje de la fuente."""

    def test_a_many_to_many_is_a_field_without_a_column(self, definition):
        # El no-almacenado que SÍ es un `models.Field`, así que `to_sql` le
        # llega y tiene que rechazarlo. (Una relación INVERSA de Django es un
        # `ForeignObjectRel` y no un `Field`: nunca recibe el método, y
        # `_fields` ya la excluye por `concrete` antes de eso.)
        m2m = django_models.ManyToManyField('base.IrModel')
        m2m.set_attributes_from_name('cualquiera')
        assert not m2m.concrete
        with pytest.raises(ValueError, match='not stored'):
            m2m.to_sql(definition, TABLE)

    def test_the_message_matches_the_reference(self, definition):
        m2m = django_models.ManyToManyField('base.IrModel')
        m2m.set_attributes_from_name('cualquiera')
        with pytest.raises(ValueError) as exc:
            m2m.to_sql(definition, TABLE)
        assert 'Cannot convert' in str(exc.value)

    def test_a_reverse_relation_never_reaches_to_sql(self):
        # Se mide desde el otro lado: no está en `_fields`, así que
        # `_field_to_sql` lo rechaza como campo inexistente antes de convertir.
        inverse = IrModelFields._meta.get_field('properties_definition_ids')
        assert not getattr(inverse, 'concrete', False)
        assert not isinstance(inverse, django_models.Field)


class TestJoin:
    """``Many2one.join`` — el LEFT JOIN que ``_traverse_related_sql`` encadena."""

    def test_it_adds_the_left_join_and_returns_comodel_and_alias(self, definition):
        query = Query(None, TABLE)
        field = definition._fields['properties_field']
        comodel, coalias = field.join(definition, TABLE, query)

        assert comodel is IrModelFields
        assert coalias == Query.make_alias(TABLE, 'properties_field')
        assert 'LEFT JOIN' in query.from_clause.code
        assert IrModelFields._meta.db_table in query.from_clause.code

    def test_the_on_condition_comes_from_field_to_sql(self, definition):
        # La condición del lado izquierdo sale del mismo punto de entrada que
        # cualquier otra columna — con su comprobación de acceso incluida.
        query = Query(None, TABLE)
        definition._fields['properties_field'].join(definition, TABLE, query)
        assert '"properties_base_definition"."properties_field_id" = ' \
            in query.from_clause.code


class TestTraverseRelatedRefusesWhatIsStored:
    """``_traverse_related_sql`` — su aserción de entrada, ≙ ``:2896``."""

    def test_a_stored_field_is_refused(self, definition):
        # La fuente abre con `assert field.related and not field.store`: el
        # recorrido es para campos derivados, no para columnas.
        with pytest.raises(AssertionError):
            definition._traverse_related_sql(
                TABLE, definition._fields['properties_definition'],
                Query(None, TABLE))


@pytest.mark.django_db
class TestAgainstTheRealSchema:
    """El SQL compuesto, corrido de verdad.

    Los bloques de arriba comparan cadenas y **nunca tocan la base**: su verde
    no distingue "el fragmento es válido" de "nadie lo ejecutó". Este cierra
    esa mitad.
    """

    @pytest.fixture
    def field_row(self):
        model = IrModel.objects.get_or_create(
            model='base.Sujeto', defaults={'name': 'Sujeto'})[0]
        return IrModelFields.objects.create(
            model_id=model, model='base.Sujeto', name='props',
            ttype='properties', state='base')

    def test_a_composed_select_runs(self, field_row):
        row = PropertiesBaseDefinition.objects.create(
            properties_field=field_row, properties_definition=[{'name': 'color'}])
        query = Query(None, TABLE)
        query.add_where(SQL("%s = %s", SQL.identifier(TABLE, 'id'), row.pk))
        assert query.get_result_ids() == (row.pk,)

    def test_the_join_it_builds_is_accepted_by_postgres(self, field_row):
        row = PropertiesBaseDefinition.objects.create(properties_field=field_row)
        definition = PropertiesBaseDefinition()
        query = Query(None, TABLE)
        comodel, coalias = definition._fields['properties_field'].join(
            definition, TABLE, query)
        query.add_where(SQL("%s = %s", SQL.identifier(coalias, 'id'), field_row.pk))
        assert query.get_result_ids() == (row.pk,)

    def test_the_json_arrow_returns_the_property(self, field_row):
        PropertiesBaseDefinition.objects.create(
            properties_field=field_row,
            properties_definition={'color': 'azul'})
        definition = PropertiesBaseDefinition()
        query = Query(None, TABLE)
        query.add_where(SQL("%s = %s", SQL.identifier(TABLE, 'properties_field_id'),
                            field_row.pk))
        rows = query._execute_query(query.select(
            definition._field_to_sql(TABLE, 'properties_definition.color')))
        # `->` devuelve **jsonb**, así que una cadena vuelve con sus
        # comillas. Es lo que la fuente emite —usa `->`, no `->>`— y por
        # eso la aserción las lleva: quitarlas sería portar otro operador.
        assert rows == [('"azul"',)]
