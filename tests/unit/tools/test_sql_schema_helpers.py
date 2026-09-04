"""Los cinco ayudantes de schema de ``tools/sql.py``, y su tabla de codigos.

La referencia los declara en ``odoo19c: odoo/tools/sql.py`` —``_CONFDELTYPES``
(``:37``), ``existing_tables`` (``:204``), ``drop_constraint`` (``:466``),
``add_foreign_key`` (``:475``), ``get_foreign_keys`` (``:487``),
``drop_index`` (``:626``) y ``make_index_name`` (``:779``)— y este archivo no
tenia ninguno. Los pide el eje de schema de ``Registry`` (tramo 4 de la tarea
**#342**): sin ellos, ``check_foreign_keys`` y ``check_indexes`` no se pueden
escribir.

**El control que discrimina** es ``test_an_invented_table_is_not_reported``:
un ``existing_tables`` que devolviera todo lo que se le pasa pasaria los casos
positivos y nadie lo notaria. El segundo es
``test_a_long_name_gets_a_hash``: sin el, un ``make_index_name`` que
devolviera el nombre tal cual pasaria el caso corto — y dos indices distintos
colapsarian en uno cuando PostgreSQL trunque a 63.
"""
import pytest
from django.db import connection

from tools.sql import (_CONFDELTYPES, add_foreign_key, drop_constraint,
                       drop_index, existing_tables, get_foreign_keys,
                       make_index_name)


@pytest.fixture
def cr(db):
    with connection.cursor() as cursor:
        yield cursor


@pytest.fixture
def two_tables(cr):
    """Dos tablas de usar y tirar, para la ida y vuelta de la clave foranea."""
    cr.execute('CREATE TABLE probe_target (id serial PRIMARY KEY)')
    cr.execute('CREATE TABLE probe_source (id serial PRIMARY KEY, target_id integer)')
    yield 'probe_source', 'probe_target'
    cr.execute('DROP TABLE IF EXISTS probe_source')
    cr.execute('DROP TABLE IF EXISTS probe_target')


class TestConfdeltypes:
    """≙ ``_CONFDELTYPES`` (``:37-43``) — la letra que PostgreSQL guarda.

    El nombre va en una sola palabra, como la constante y como la columna
    ``confdeltype`` de ``pg_constraint`` que le da el nombre. Partido en
    ``Conf`` + ``Del`` + ``Types``, el gate de idioma lee ``Del`` como la
    particula espanola y marca el identificador; la columna se llama asi en
    PostgreSQL y el nombre la sigue.
    """

    def test_it_declares_the_five_of_the_reference(self):
        assert _CONFDELTYPES == {
            'RESTRICT': 'r',
            'NO ACTION': 'a',
            'CASCADE': 'c',
            'SET NULL': 'n',
            'SET DEFAULT': 'd',
        }


class TestMakeIndexName:
    """≙ ``make_index_name`` (``:779-781``)."""

    def test_it_follows_the_convention(self):
        assert make_index_name('res_partner', 'name') == 'res_partner__name_index'

    def test_a_long_name_gets_a_hash(self):
        """El control: sin recorte, dos indices distintos colapsan en uno."""
        table = 'a' * 40
        name = make_index_name(table, 'b' * 40)
        assert len(name) <= 63
        assert name != f'{table}__{"b" * 40}_index'

    def test_two_long_names_do_not_collide(self):
        first = make_index_name('t' * 40, 'primero' + 'x' * 30)
        second = make_index_name('t' * 40, 'segundo' + 'x' * 30)
        assert first != second


class TestExistingTables:
    """≙ ``existing_tables`` (``:204-213``)."""

    def test_a_real_table_is_reported(self, cr):
        assert 'res_partner' in existing_tables(cr, {'res_partner'})

    def test_an_invented_table_is_not_reported(self, cr):
        """El control: sin esto, un ayudante que devuelva su entrada pasaria."""
        assert existing_tables(cr, {'no_existe_esta_tabla'}) == []

    def test_it_filters_the_mix(self, cr):
        found = existing_tables(cr, {'res_partner', 'no_existe_esta_tabla'})
        assert found == ['res_partner']


class TestForeignKeyRoundTrip:
    """≙ ``add_foreign_key`` · ``get_foreign_keys`` · ``drop_constraint``."""

    def test_there_is_none_before_adding_it(self, cr, two_tables):
        source, target = two_tables
        assert get_foreign_keys(cr, source, 'target_id', target, 'id', 'cascade') == []

    def test_adding_it_makes_it_findable(self, cr, two_tables):
        source, target = two_tables
        add_foreign_key(cr, source, 'target_id', target, 'id', 'cascade')
        names = get_foreign_keys(cr, source, 'target_id', target, 'id', 'cascade')
        assert len(names) == 1
        assert isinstance(names[0], str)

    def test_the_delete_policy_discriminates(self, cr, two_tables):
        """El control: la busqueda filtra por ``confdeltype``, no solo por columna."""
        source, target = two_tables
        add_foreign_key(cr, source, 'target_id', target, 'id', 'cascade')
        assert get_foreign_keys(cr, source, 'target_id', target, 'id', 'restrict') == []

    def test_dropping_it_leaves_nothing(self, cr, two_tables):
        source, target = two_tables
        add_foreign_key(cr, source, 'target_id', target, 'id', 'cascade')
        name = get_foreign_keys(cr, source, 'target_id', target, 'id', 'cascade')[0]
        drop_constraint(cr, source, name)
        assert get_foreign_keys(cr, source, 'target_id', target, 'id', 'cascade') == []


class TestDropIndex:
    """≙ ``drop_index`` (``:626-629``) — con ``IF EXISTS``, como la fuente."""

    def test_dropping_an_absent_index_is_a_no_op(self, cr):
        drop_index(cr, 'no_existe_este_indice', 'res_partner')

    def test_it_drops_the_index(self, cr, two_tables):
        source, _ = two_tables
        cr.execute(f'CREATE INDEX probe_source__target_id_index ON {source} (target_id)')
        drop_index(cr, 'probe_source__target_id_index', source)
        cr.execute("SELECT 1 FROM pg_class WHERE relname = 'probe_source__target_id_index'")
        assert cr.fetchall() == []
