"""``Registry`` tramo 4 — el eje de schema.

Los seis simbolos que la referencia declara entre ``check_null_constraints``
(``odoo19c: odoo/orm/registry.py:779``) e ``is_an_ordinary_table``
(``:1001``). Ninguno existia aqui: ``init`` declaraba ``_ordinary_tables`` y
``_sql_constraints`` como atributos y **nadie los leia ni los escribia**.

Los cinco ayudantes de ``tools/sql.py`` que estos metodos piden se prueban por
separado en ``tests/unit/tools/test_sql_schema_helpers.py``.

**Los controles que discriminan**, uno por metodo con veredicto binario:

- ``test_a_nullable_column_does_not_enter`` — un ``check_null_constraints``
  que metiera todo campo declarado ``required`` pasaria el caso positivo. Lo
  que la fuente cruza es el **esquema** contra la declaracion, y el aviso
  existe justo para cuando no coinciden.
- ``test_not_forcing_keeps_the_first`` — ``add_foreign_key(force=False)`` usa
  ``setdefault``; sin este caso, un ``force`` ignorado no se notaria.
- ``test_a_view_is_not_an_ordinary_table`` — ``is_an_ordinary_table`` filtra
  por ``relkind = 'r'``. Una vista existe y **no** es tabla ordinaria: sin
  este caso, un filtro por existencia a secas pasaria.
"""
import logging
import warnings

import pytest
from django.apps import apps
from django.db import connection

from orm.registry import Registry


@pytest.fixture
def registry(db):
    Registry.delete_all()
    built = Registry('default')
    yield built
    Registry.delete_all()


@pytest.fixture
def cr(db):
    with connection.cursor() as cursor:
        yield cursor


@pytest.fixture
def scratch_table(cr):
    """Una tabla con una columna que rechaza el nulo y otra que no."""
    cr.execute('DROP TABLE IF EXISTS probe_schema')
    cr.execute('CREATE TABLE probe_schema ('
               ' id serial PRIMARY KEY,'
               ' firm text NOT NULL,'
               ' loose text)')
    yield 'probe_schema'
    cr.execute('DROP TABLE IF EXISTS probe_schema')


class _Field:
    """Un doble de campo: lo que el eje de schema mira, y nada mas.

    **Un doble con atributos esconde el acceso a un atributo.** Este llevaba
    los seis que el eje lee y ninguno mas, asi que los cinco casos de
    ``TestCheckIndexes`` pasaban en verde mientras el recorrido real reventaba
    contra un modelo de Django — que declara ``_fields`` de otra forma y mete
    en el mapa objetos que no son campos. El control que lo discrimina no es un
    doble mejor: es
    :meth:`TestCheckIndexes.test_it_walks_a_real_model_without_breaking`, que
    no usa doble ninguno.
    """

    def __init__(self, name, *, column_type=('text', 'TEXT'), store=True,
                 required=True, index=None, translate=False,
                 company_dependent=False, concrete=True):
        self.name = name
        self.column_type = column_type
        self.store = store
        self.required = required
        self.index = index
        self.translate = translate
        self.company_dependent = company_dependent
        #: El nombre de Django para «tiene columna». El filtro de
        #: ``check_indexes`` lo pregunta primero porque es el unico que los
        #: objetos de relacion inversa declaran.
        self.concrete = concrete


class _Meta:
    def __init__(self, *, managed=True, abstract=False):
        self.managed = managed
        self.abstract = abstract


class _Model:
    def __init__(self, name, table, fields, *, managed=True, abstract=False):
        self._name = name
        self._table = table
        self._fields = {field.name: field for field in fields}
        self._meta = _Meta(managed=managed, abstract=abstract)


class TestCheckNullConstraints:
    """≙ ``check_null_constraints`` (``:779-803``)."""

    def test_a_not_null_column_enters(self, registry, cr, scratch_table):
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('firm')])}
        registry.check_null_constraints(cr)
        names = {field.name for field in registry.not_null_fields}
        assert 'firm' in names

    def test_a_nullable_column_does_not_enter(self, registry, cr, scratch_table):
        """El control: lo que decide es el esquema, no lo que el campo declara."""
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('loose')])}
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            registry.check_null_constraints(cr)
        names = {field.name for field in registry.not_null_fields}
        assert 'loose' not in names

    def test_the_primary_key_enters_without_asking_the_schema(self, registry, cr,
                                                              scratch_table):
        """≙ la rama ``field_name == 'id'`` de la fuente (``:795-797``)."""
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table,
            [_Field('id', required=False, store=False, column_type=None)])}
        registry.check_null_constraints(cr)
        assert {field.name for field in registry.not_null_fields} == {'id'}

    def test_an_unmanaged_model_is_skipped(self, registry, cr, scratch_table):
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('firm')], managed=False)}
        registry.check_null_constraints(cr)
        assert registry.not_null_fields == set()

    def test_it_replaces_what_was_there(self, registry, cr, scratch_table):
        """La fuente limpia antes de rellenar (``:791``)."""
        registry.not_null_fields.add(object())
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('firm')])}
        registry.check_null_constraints(cr)
        assert len(registry.not_null_fields) == 1


class TestCheckIndexes:
    """≙ ``check_indexes`` (``:805-892``)."""

    def test_it_creates_the_expected_index(self, registry, cr, scratch_table):
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('firm', index='btree')])}
        registry.check_indexes(cr, ['x.probe'])
        cr.execute("SELECT 1 FROM pg_class WHERE relname = %s",
                   ['probe_schema__firm_index'])
        assert cr.fetchall() == [(1,)]
        cr.execute('DROP INDEX IF EXISTS probe_schema__firm_index')

    def test_a_field_without_index_gets_none(self, registry, cr, scratch_table):
        """El control: sin esto, crear siempre pasaria el caso positivo."""
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('firm', index=None)])}
        registry.check_indexes(cr, ['x.probe'])
        cr.execute("SELECT 1 FROM pg_class WHERE relname = %s",
                   ['probe_schema__firm_index'])
        assert cr.fetchall() == []

    def test_an_empty_expectation_is_a_no_op(self, registry, cr):
        registry.models = {}
        registry.check_indexes(cr, [])

    def test_it_walks_a_real_model_without_breaking(self, registry, cr):
        """El control: un modelo de verdad, sin dobles.

        ``res.partner`` mete en su ``_fields`` 36 ``ManyToOneRel``, 4
        ``OneToOneRel``, 2 ``ManyToManyRel`` y 16 ``NonStored``: ninguno es un
        campo con columna, y ninguno respondia a ``column_type``. Con el doble
        de arriba eso no se veia — todos sus campos contestan a todo.

        No afirma que se cree indice alguno; afirma que el recorrido **llega al
        final**, que es lo que el porte prometia y no cumplia.
        """
        registry.check_indexes(cr, ['res.partner'])

    def test_the_field_registry_answers_from_the_class(self, registry):
        """``Model._fields`` sin instanciar — ≙ ``odoo19c: registry.py:813``.

        Es la precondicion del caso anterior: si ``_fields`` fuera una
        ``property``, sobre la clase devolveria el descriptor y el ``.values()``
        de ``check_indexes`` fallaria antes de mirar ningun campo.
        """
        partner = apps.get_model('base', 'ResPartner')
        registry_map = partner._fields
        assert isinstance(registry_map, dict)
        assert 'name' in registry_map

    def test_a_partial_index_carries_its_condition(self, registry, cr, scratch_table):
        registry.models = {'x.probe': _Model(
            'x.probe', scratch_table, [_Field('loose', index='btree_not_null')])}
        registry.check_indexes(cr, ['x.probe'])
        cr.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s",
                   ['probe_schema__loose_index'])
        rows = cr.fetchall()
        assert rows and 'WHERE' in rows[0][0]
        cr.execute('DROP INDEX IF EXISTS probe_schema__loose_index')


class TestAddForeignKey:
    """≙ ``add_foreign_key`` (``:894-905``) — sólo anota lo esperado."""

    @pytest.fixture(autouse=True)
    def queue(self, registry):
        registry._foreign_keys = {}

    def test_it_records_the_expectation(self, registry):
        registry.add_foreign_key('a', 'b_id', 'b', 'id', 'cascade', None, 'base')
        assert registry._foreign_keys[('a', 'b_id')] == ('b', 'id', 'cascade', None, 'base')

    def test_forcing_replaces(self, registry):
        registry.add_foreign_key('a', 'b_id', 'b', 'id', 'cascade', None, 'base')
        registry.add_foreign_key('a', 'b_id', 'c', 'id', 'restrict', None, 'sale')
        assert registry._foreign_keys[('a', 'b_id')][0] == 'c'

    def test_not_forcing_keeps_the_first(self, registry):
        """El control: ``force=False`` es ``setdefault``, no ``update``."""
        registry.add_foreign_key('a', 'b_id', 'b', 'id', 'cascade', None, 'base')
        registry.add_foreign_key('a', 'b_id', 'c', 'id', 'restrict', None, 'sale',
                                 force=False)
        assert registry._foreign_keys[('a', 'b_id')][0] == 'b'


class TestCheckForeignKeys:
    """≙ ``check_foreign_keys`` (``:907-943``)."""

    def test_an_empty_queue_is_a_no_op(self, registry, cr):
        registry._foreign_keys = {}
        registry.check_foreign_keys(cr)

    def test_it_creates_the_missing_key(self, registry, cr):
        cr.execute('DROP TABLE IF EXISTS probe_source')
        cr.execute('DROP TABLE IF EXISTS probe_target')
        cr.execute('CREATE TABLE probe_target (id serial PRIMARY KEY)')
        cr.execute('CREATE TABLE probe_source (id serial PRIMARY KEY, target_id integer)')
        try:
            registry._foreign_keys = {
                ('probe_source', 'target_id'):
                    ('probe_target', 'id', 'cascade', None, 'base')}
            registry.check_foreign_keys(cr)
            cr.execute("SELECT 1 FROM pg_constraint WHERE contype = 'f'"
                       " AND conrelid = 'probe_source'::regclass")
            assert cr.fetchall() == [(1,)]
        finally:
            cr.execute('DROP TABLE IF EXISTS probe_source')
            cr.execute('DROP TABLE IF EXISTS probe_target')


class TestCheckTablesExist:
    """≙ ``check_tables_exist`` (``:945-...``) — avisa, no crea."""

    def test_a_present_table_reports_nothing(self, registry, cr, caplog):
        caplog.set_level(logging.INFO, logger='kaupamex.registry')
        registry.models = {'x.probe': _Model(
            'x.probe', 'res_partner', [])}
        registry.check_tables_exist(cr)
        assert 'Models have no table' not in caplog.text

    def test_a_missing_table_is_named(self, registry, cr, caplog):
        """La fuente avisa en ``info``, no en ``warning`` — por eso el nivel."""
        caplog.set_level(logging.INFO, logger='kaupamex.registry')
        registry.models = {'x.absent': _Model(
            'x.absent', 'no_existe_esta_tabla', [])}
        registry.check_tables_exist(cr)
        assert 'x.absent' in caplog.text


class TestIsAnOrdinaryTable:
    """≙ ``is_an_ordinary_table`` (``:1001-1016``)."""

    @pytest.fixture
    def a_view(self, cr):
        cr.execute('DROP VIEW IF EXISTS probe_view')
        cr.execute('CREATE VIEW probe_view AS SELECT 1 AS id')
        yield 'probe_view'
        cr.execute('DROP VIEW IF EXISTS probe_view')

    def test_a_real_table_is_ordinary(self, registry):
        partner = apps.get_model('base', 'ResPartner')
        assert registry.is_an_ordinary_table(partner) is True

    def test_a_view_is_not_an_ordinary_table(self, registry, a_view):
        """El control: existir no basta — la fuente filtra por ``relkind = 'r'``."""
        registry.models = {'x.view': _Model('x.view', a_view, [])}
        registry._ordinary_tables = None
        assert registry.is_an_ordinary_table(registry.models['x.view']) is False

    def test_the_answer_is_memoised(self, registry):
        partner = apps.get_model('base', 'ResPartner')
        registry._ordinary_tables = None
        registry.is_an_ordinary_table(partner)
        assert registry._ordinary_tables is not None
        assert 'res_partner' in registry._ordinary_tables
