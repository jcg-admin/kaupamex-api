"""Los objetos de tabla: el contrato de ``odoo/orm/table_objects.py``.

La fuente declara cuatro clases —``TableObject``, ``Constraint``, ``Index`` y
``UniqueIndex``— con quince simbolos entre atributos y metodos. El arbol tenia
en su lugar **tres alias** a los constructos nativos de Django, con firmas
incompatibles: ``Constraint = CheckConstraint`` recibe su condicion por
palabra clave, y la fuente la pasa posicional. Ningun test lo media.

Lo que Django SI trae es el motor de esquema, asi que ``apply_to_database``
diverge de mecanismo — emite por el editor de esquema en vez de componer el
DDL a mano. Lo que Django NO trae, y por eso se construye aqui:

- el **nombrado por atributo de clase** (``__set_name__``), con su contrato de
  guion bajo inicial y su prohibicion de nombre mangleado;
- el **nombre completo** ``{tabla}_{nombre}``, acotado a 63 caracteres;
- el **mensaje de violacion invocable**, que recibe el entorno y el
  diagnostico. El ``violation_error_message`` de Django es una cadena fija.

Medido antes de construir (``scripts/workbench/table-object-naming-*``):
``__set_name__`` **si** se dispara en el cuerpo de un modelo de Django, y en
ese instante ``_meta`` **aun no existe** — de ahi que el registro vaya a una
lista de clase y no a ``Meta.constraints``.
"""
import pytest
from django.db import connection
from django.db import models as django_models

from orm.table_objects import Constraint, Index, TableObject, UniqueIndex


class _FakeMeta:
    def __init__(self, table):
        self.db_table = table


class _FakeModel:
    """Un modelo minimo: solo lo que ``full_name`` necesita."""

    def __init__(self, table='res_partner'):
        self._table = table
        self._meta = _FakeMeta(table)


class TestTheNamingProtocol:
    """``__set_name__`` — el nombre sale del atributo que lo aloja."""

    def test_the_attribute_names_the_object_without_its_underscore(self):
        class Holder:
            _name_uniq = Constraint('unique (name)')

        assert Holder._name_uniq.name == 'name_uniq'

    def test_a_name_without_leading_underscore_is_rejected(self):
        with pytest.raises(AssertionError, match="guion bajo|start with"):
            class Holder:
                name_uniq = Constraint('unique (name)')

    def test_a_mangled_name_is_rejected(self):
        with pytest.raises(AssertionError, match="mangle"):
            class Holder:
                __name_uniq = Constraint('unique (name)')

    def test_the_object_registers_itself_on_the_owner(self):
        class Holder:
            _a = Constraint('unique (a)')
            _b = Index('(b)')

        registered = [o.name for o in Holder._table_object_definitions]
        assert registered == ['a', 'b']

    def test_it_fires_inside_a_django_model_body(self):
        class Holder(django_models.Model):
            _name_uniq = Constraint('unique (name)')
            label = django_models.CharField(max_length=8)

            class Meta:
                app_label = 'base'
                managed = False
                db_table = 'zz_table_objects_probe'

        assert Holder._name_uniq.name == 'name_uniq'


class TestTheFullName:
    """``full_name`` — ``{tabla}_{nombre}``, por ``make_identifier``."""

    def test_it_prefixes_the_table(self):
        obj = Constraint('unique (name)')
        obj.__set_name__(_FakeModel, '_name_uniq')
        assert obj.full_name(_FakeModel()) == 'res_partner_name_uniq'

    def test_an_unnamed_object_refuses_to_compose_a_name(self):
        with pytest.raises(AssertionError):
            Constraint('unique (name)').full_name(_FakeModel())

    def test_it_is_capped_at_the_postgresql_limit(self):
        obj = Constraint('unique (name)')
        obj.__set_name__(_FakeModel, '_' + 'x' * 70)
        composed = obj.full_name(_FakeModel())
        assert len(composed) == 63


class TestTheViolationMessage:
    """``get_error_message`` — lo que Django no trae: mensaje invocable."""

    def test_a_plain_string_comes_back_verbatim(self):
        obj = Constraint('unique (name)', 'El nombre debe ser unico')
        assert obj.get_error_message(_FakeModel()) == 'El nombre debe ser unico'

    def test_a_callable_receives_the_environment_and_the_diagnostics(self):
        seen = {}

        def build(env, diagnostics):
            seen['env'] = env
            seen['diagnostics'] = diagnostics
            return 'compuesto'

        obj = Constraint('unique (name)', build)
        model = _FakeModel()
        model.env = 'ENTORNO'
        assert obj.get_error_message(model, diagnostics='DIAG') == 'compuesto'
        assert seen == {'env': 'ENTORNO', 'diagnostics': 'DIAG'}

    def test_without_a_message_it_is_the_empty_string(self):
        assert Constraint('unique (name)').get_error_message(_FakeModel()) == ''


class TestTheDefinitions:
    """``get_definition`` — su forma difiere entre las tres subclases."""

    def test_a_constraint_returns_its_sql_verbatim(self):
        assert Constraint('CHECK (x > 0)').get_definition(None) == 'CHECK (x > 0)'

    def test_an_index_wraps_its_definition_with_the_keyword(self):
        assert Index('(group_id, active)').get_definition(None) == \
            'INDEX (group_id, active)'

    def test_a_unique_index_declares_its_uniqueness(self):
        assert UniqueIndex('(group_id)').get_definition(None) == \
            'UNIQUE INDEX (group_id)'

    def test_an_index_definition_may_be_callable_on_the_registry(self):
        obj = Index(lambda registry: f'({registry})')
        assert obj.get_definition('REG') == 'INDEX (REG)'

    def test_an_empty_definition_produces_no_index(self):
        assert Index(lambda registry: '').get_definition('REG') == ''


class TestTheClassContract:
    """Los quince simbolos que la fuente declara, medidos por nombre."""

    def test_the_base_declares_its_three_class_attributes(self):
        assert TableObject.message == ''
        assert TableObject._module == ''
        assert 'name' in TableObject.__annotations__

    def test_the_subclasses_descend_from_the_base(self):
        assert issubclass(Constraint, TableObject)
        assert issubclass(Index, TableObject)
        assert issubclass(UniqueIndex, Index)

    def test_only_the_unique_index_declares_uniqueness(self):
        assert Index.unique is False
        assert UniqueIndex.unique is True

    def test_the_base_refuses_to_define_or_apply_by_itself(self):
        obj = TableObject()
        with pytest.raises(NotImplementedError):
            obj.get_definition(None)
        with pytest.raises(NotImplementedError):
            obj.apply_to_database(_FakeModel())

    def test_its_repr_carries_name_definition_and_message(self):
        obj = Constraint('unique (name)', 'unico')
        obj.__set_name__(_FakeModel, '_name_uniq')
        rendered = str(obj)
        assert 'name_uniq' in rendered
        assert 'unique (name)' in rendered
        assert 'unico' in rendered


@pytest.mark.django_db
class TestTheBridgeToDjango:
    """``to_django`` — el puente al motor de esquema, construido.

    Se asierta el **SQL emitido**, no la clase que lo emite. Django no trae
    ninguna clase que acepte SQL crudo: ``CheckConstraint`` exige un ``Q`` o
    una expresion booleana y rechaza el resto con ``TypeError``, y el universo
    de la fuente es mas ancho que el ``CHECK`` — sus propios ejemplos incluyen
    ``FOREIGN KEY (abc) REFERENCES some_table(id)``.
    """

    def test_a_constraint_carries_its_full_name(self):
        obj = Constraint('CHECK (credit_limit > 0)', 'Limite invalido')
        obj.__set_name__(_FakeModel, '_credit_positive')
        native = obj.to_django(_FakeModel())
        assert isinstance(native, django_models.BaseConstraint)
        assert native.name == 'res_partner_credit_positive'

    def test_a_constraint_emits_its_definition_verbatim(self):
        obj = Constraint('FOREIGN KEY (abc) REFERENCES some_table(id)')
        obj.__set_name__(_FakeModel, '_abc_fk')
        native = obj.to_django(_FakeModel())
        with connection.schema_editor(collect_sql=True) as editor:
            emitted = native.constraint_sql(_FakeModel(), editor)
        assert 'FOREIGN KEY (abc) REFERENCES some_table(id)' in emitted
        assert 'res_partner_abc_fk' in emitted

    def test_a_unique_index_emits_create_unique_index(self):
        obj = UniqueIndex('(login)')
        obj.__set_name__(_FakeModel, '_login_uniq')
        native = obj.to_django(_FakeModel())
        with connection.schema_editor(collect_sql=True) as editor:
            emitted = str(native.create_sql(_FakeModel(), editor))
        assert 'CREATE UNIQUE INDEX' in emitted
        assert '(login)' in emitted

    def test_a_plain_index_emits_create_index_without_uniqueness(self):
        obj = Index('(group_id, active) WHERE active IS TRUE')
        obj.__set_name__(_FakeModel, '_group_active')
        native = obj.to_django(_FakeModel())
        with connection.schema_editor(collect_sql=True) as editor:
            emitted = str(native.create_sql(_FakeModel(), editor))
        assert 'CREATE INDEX' in emitted
        assert 'UNIQUE' not in emitted
        assert 'WHERE active IS TRUE' in emitted

    def test_the_violation_message_travels_to_the_native_constraint(self):
        obj = Constraint('CHECK (x > 0)', 'x debe ser positivo')
        obj.__set_name__(_FakeModel, '_x_positive')
        native = obj.to_django(_FakeModel())
        assert native.violation_error_message == 'x debe ser positivo'


class TestTheAliasIsGone:
    """Control discriminante: el alias que el porte retira.

    Si alguien reintroduce ``Constraint = CheckConstraint``, este caso cae —
    el nativo de Django no acepta su condicion posicional, y la fuente la pasa
    asi en las 47 declaraciones medidas del arbol.
    """

    def test_the_constraint_takes_its_definition_positionally(self):
        obj = Constraint('unique (name)')
        assert obj.get_definition(None) == 'unique (name)'

    def test_it_is_not_djangos_check_constraint(self):
        assert not issubclass(Constraint, django_models.BaseConstraint)


class TestIndexSplitsByTheShapeOfTheCall:
    """Un solo ``Index`` para los dos usos — el reparto medido de #321.

    ``odoo19c: odoo/models/__init__.py`` re-exporta ``Index`` desde
    ``odoo/orm/table_objects.py``: el objeto de tabla, con su definicion SQL
    **posicional**. Aqui la fachada ``models`` tambien entrega la superficie de
    Django, donde ``Index`` se escribe con **palabras clave** en
    ``Meta.indexes`` — y son 51 sitios reales.

    Las dos poblaciones son disjuntas en el arbol (medido por AST: 51 con solo
    palabras clave, 0 con posicional), asi que el constructor las reparte sin
    ambiguedad. No es una heuristica sobre lo que Django acepte: Django **si**
    admite un ``str`` posicional y lo envuelve en ``F(...)`` sin quejarse, asi
    que el reparto es una decision nuestra, explicita y probada aqui.
    """

    def test_a_positional_string_is_the_table_object(self):
        """EL CONTROL DE LA FRONTERA.

        Fija la decision para que sea leida y no descubierta: un ``str``
        posicional es la definicion SQL de la referencia, no la expresion que
        Django construiria. Bajo la version anterior ese mismo argumento daba
        ``F('(active) WHERE active IS TRUE')`` — un nombre de columna imposible
        que falla al resolver, no al escribirse.
        """
        obj = Index('(active) WHERE active IS TRUE')
        assert isinstance(obj, Index)
        assert obj.get_definition(None) == 'INDEX (active) WHERE active IS TRUE'

    def test_a_positional_callable_is_the_table_object(self):
        """La fuente admite un invocable que recibe el registro."""
        obj = Index(lambda registry: '(group_id, user_id)')
        assert isinstance(obj, Index)
        assert obj.get_definition(None) == 'INDEX (group_id, user_id)'

    def test_keywords_only_give_djangos_index(self):
        """Los 51 sitios de ``Meta.indexes`` siguen recibiendo el de Django."""
        obj = Index(fields=['name'], name='res_partner_name_idx')
        assert type(obj) is django_models.Index
        assert obj.fields == ['name']
        assert obj.name == 'res_partner_name_idx'

    def test_the_django_branch_keeps_its_migration_identity(self):
        """EL CONTROL que protege las migraciones ya escritas.

        ``deconstruct`` es lo que una migracion guarda. Si la rama de Django
        devolviera una subclase nuestra, las 51 migraciones existentes dejarian
        de reconstruirse con el mismo objeto y ``makemigrations`` propondria un
        cambio que nadie pidio.
        """
        ruta, _, _ = Index(fields=['name'], name='x_idx').deconstruct()
        assert ruta == 'django.db.models.Index'

    def test_a_condition_travels_to_the_django_branch(self):
        """La forma que los indices parciales del arbol usan."""
        obj = Index(fields=['active'], name='x_idx',
                    condition=django_models.Q(active=True))
        assert type(obj) is django_models.Index
        assert obj.condition == django_models.Q(active=True)

    def test_the_unique_index_refuses_the_django_shape(self):
        """EL CONTROL de la herencia.

        ``UniqueIndex`` hereda el reparto, y la rama de Django devolveria un
        ``Index`` **no unico**: la unicidad se perderia en silencio, que es
        justo el modo de fallo que un reparto por forma puede introducir. En
        Django lo unico es ``UniqueConstraint``, no un ``Index``, asi que la
        rama no tiene destino y el constructor lo dice.
        """
        with pytest.raises(TypeError, match='UniqueIndex'):
            UniqueIndex(fields=['name'], name='x_idx')

    def test_the_unique_index_still_takes_its_definition_positionally(self):
        obj = UniqueIndex('(name) WHERE active')
        assert isinstance(obj, UniqueIndex)
        assert obj.get_definition(None) == 'UNIQUE INDEX (name) WHERE active'

    def test_it_refuses_a_call_with_neither_shape(self):
        """Ni posicional ni las palabras clave que Django exige."""
        with pytest.raises((TypeError, ValueError)):
            Index()
