"""``_check_removed_columns``, ``_add_sql_constraints`` y ``_auto_init``.

≙ ``odoo19c: odoo/orm/models.py:3109-3136, 3170-3248, 3262-3268``
(``abe4040ec1``). Se portan como conciliación tras ``migrate``: cada paso
comprueba antes de actuar, así que sobre un esquema sincronizado no emite
nada. Diseño: ``designs/schema-and-translation-symbols-decision.md``,
revisión «los tres símbolos se portan con su contrato» (s1-s4).
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from orm.environments import Environment
from orm.registry import Registry
from orm.table_objects import Index
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

TABLE = 'test_orm_category'


@pytest.fixture
def env(db, system_user):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


def _nullable(column):
    with connection.cursor() as cr:
        cr.execute(
            'SELECT is_nullable FROM information_schema.columns '
            'WHERE table_name = %s AND column_name = %s', [TABLE, column])
        return cr.fetchone()[0]


def _orphan_column():
    """Una columna ``NOT NULL`` que el modelo no declara — la que deja un
    campo retirado o un módulo que la añadía."""
    with connection.cursor() as cr:
        cr.execute(f'ALTER TABLE {TABLE} ADD COLUMN orphan_flag integer '
                   'NOT NULL DEFAULT 0')


def test_an_orphan_column_loses_its_not_null(env):
    _orphan_column()
    assert _nullable('orphan_flag') == 'NO'
    env['test_orm.category']._check_removed_columns()
    assert _nullable('orphan_flag') == 'YES'


def test_a_declared_column_keeps_its_not_null(env):
    _orphan_column()
    env['test_orm.category']._check_removed_columns()
    assert _nullable('name') == 'NO'
    assert _nullable('id') == 'NO'


# --- s2: _add_sql_constraints y Constraint.apply_to_database --------------

CONSTRAINT = 'test_orm_category_positive_color'


def _constraint():
    """``(oid, definición normalizada, comentario)`` o ``None``."""
    with connection.cursor() as cr:
        cr.execute(
            'SELECT c.oid, pg_get_constraintdef(c.oid), d.description '
            'FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid '
            'LEFT JOIN pg_description d ON d.objoid = c.oid '
            'WHERE t.relname = %s AND c.conname = %s', [TABLE, CONSTRAINT])
        return cr.fetchone()


def _execute(statement):
    with connection.cursor() as cr:
        cr.execute(statement)


def test_a_migrated_equivalent_constraint_is_not_recreated(env):
    """Creada por la migración, sin comentario: equivalente por su forma
    normalizada. No se recrea; sólo recibe el comentario de la fuente.

    El estado se fija aquí: la instalación de la sesión ya concilia la base
    de pruebas, así que la restricción llega con su comentario."""
    _execute(f'COMMENT ON CONSTRAINT {CONSTRAINT} ON {TABLE} IS NULL')
    oid, definition, comment = _constraint()
    assert comment is None
    env['test_orm.category']._add_sql_constraints()
    after = _constraint()
    assert after[0] == oid
    assert after[1] == definition
    assert after[2] == 'CHECK(color >= 0)'


def test_a_second_run_changes_nothing(env):
    env['test_orm.category']._add_sql_constraints()
    first = _constraint()
    env['test_orm.category']._add_sql_constraints()
    assert _constraint() == first


def test_an_absent_constraint_is_restored(env):
    """El estado de migraciones dice que existe: se repone."""
    _execute(f'ALTER TABLE {TABLE} DROP CONSTRAINT {CONSTRAINT}')
    assert _constraint() is None
    env['test_orm.category']._add_sql_constraints()
    oid, definition, comment = _constraint()
    assert definition == 'CHECK ((color >= 0))'
    assert comment == 'CHECK(color >= 0)'


def test_a_different_constraint_is_reported_not_recreated(env, caplog):
    """La definición nueva llega por migración; aquí se informa."""
    _execute(f'ALTER TABLE {TABLE} DROP CONSTRAINT {CONSTRAINT}')
    _execute(f'ALTER TABLE {TABLE} ADD CONSTRAINT {CONSTRAINT} '
             'CHECK (color >= 5)')
    oid = _constraint()[0]
    env['test_orm.category']._add_sql_constraints()
    assert _constraint()[0] == oid
    assert _constraint()[1] == 'CHECK ((color >= 5))'
    assert CONSTRAINT in caplog.text


# --- s2: Index.apply_to_database ------------------------------------------

def _index():
    with connection.cursor() as cr:
        cr.execute(
            'SELECT c.oid, d.description FROM pg_class c '
            'LEFT JOIN pg_description d ON d.objoid = c.oid '
            "WHERE c.relname = %s AND c.relkind = 'i'",
            [f'{TABLE}_name_probe_idx'])
        return cr.fetchone()


@pytest.fixture
def name_index(env):
    """Un índice declarado como en la fuente (``models.Index('(name)')``)."""
    model = type(env['test_orm.category'])
    obj = Index('(name)')
    obj.__set_name__(model, '_name_probe_idx')
    return model, obj


def test_an_absent_index_is_created_with_its_comment(name_index):
    model, obj = name_index
    assert _index() is None
    obj.apply_to_database(model)
    assert _index()[1] == obj.get_definition(None)


def test_a_second_index_run_changes_nothing(name_index):
    model, obj = name_index
    obj.apply_to_database(model)
    first = _index()
    obj.apply_to_database(model)
    assert _index() == first


def test_an_index_without_comment_is_kept(name_index, caplog):
    """≙ ``:159``: «if we have an index without a comment (this is used by
    support to tweak indexes)». Se conserva en silencio: no es una
    diferencia que informar."""
    model, obj = name_index
    _execute(f'CREATE INDEX {TABLE}_name_probe_idx ON {TABLE} (name, id)')
    oid = _index()[0]
    obj.apply_to_database(model)
    assert _index() == (oid, None)
    assert 'name_probe_idx' not in caplog.text


# --- s3: _auto_init -------------------------------------------------------

def test_on_a_synchronised_schema_it_emits_no_schema_ddl(env):
    """Con el esquema que dejó la migración, la conciliación no cambia la
    forma de nada: ningún ``CREATE``/``ALTER``/``DROP``."""
    model = type(env['test_orm.category'])
    model._add_sql_constraints()   # adopta el comentario de la migración
    with CaptureQueriesContext(connection) as queries:
        model._auto_init()
    ddl = [q['sql'] for q in queries.captured_queries
           if q['sql'].lstrip().upper().startswith(('CREATE', 'ALTER',
                                                    'DROP'))]
    assert ddl == []


def test_it_relaxes_an_orphan_column(env):
    _orphan_column()
    type(env['test_orm.category'])._auto_init()
    assert _nullable('orphan_flag') == 'YES'


def test_a_missing_declared_column_names_its_migration(env):
    """La columna declarada nace de una migración; si falta, se nombra en
    vez de crearla fuera del estado de migraciones."""
    _execute(f'ALTER TABLE {TABLE} DROP COLUMN color')
    with pytest.raises(ValueError, match='color'):
        type(env['test_orm.category'])._auto_init()


def test_a_missing_table_names_its_migration(env):
    _execute(f'ALTER TABLE {TABLE} RENAME TO {TABLE}_moved')
    with pytest.raises(ValueError, match=f'Table {TABLE} '):
        type(env['test_orm.category'])._auto_init()


# --- s4: el ciclo de instalación llama a _auto_init -----------------------

def test_init_models_runs_the_reconciliation(env):
    """≙ ``Registry.init_models`` (``odoo19c: odoo/orm/registry.py:750-752``):
    cada modelo pasa por ``_auto_init`` antes del reflejo."""
    _orphan_column()
    registry = Registry(connection.alias)
    with connection.cursor() as cr:
        registry.init_models(cr, ['test_orm.category'],
                             {'module': 'test_orm'}, install=False)
    assert _nullable('orphan_flag') == 'YES'


# --- s5: el gancho init, tras _auto_init ----------------------------------

VIEW = 'hr_employee_public'


def _relkind(name):
    with connection.cursor() as cr:
        cr.execute('SELECT relkind FROM pg_class WHERE relname = %s', [name])
        row = cr.fetchone()
        return row[0] if row else None


def _drop_view():
    with connection.cursor() as cr:
        cr.execute(f'DROP VIEW IF EXISTS {VIEW}')


def test_the_base_init_hook_emits_nothing(env):
    """≙ ``BaseModel.init`` (``odoo19c: odoo/orm/models.py:3250-3253``): el
    gancho base no toca el esquema."""
    with CaptureQueriesContext(connection) as queries:
        Registry(connection.alias).models['test_orm.category'].init(
            using=connection.alias)
    assert len(queries) == 0


def test_init_models_creates_the_view_of_an_unmanaged_model(env):
    """``hr.employee.public`` no tiene tabla (``_auto = False``): su vista la
    crea su ``init`` cuando ``init_models`` lo llama tras ``_auto_init``
    (``odoo19c: odoo/orm/registry.py:751-752``)."""
    _drop_view()
    registry = Registry(connection.alias)
    with connection.cursor() as cr:
        registry.init_models(cr, ['hr.employee.public'],
                             {'module': 'hr'}, install=False)
    assert _relkind(VIEW) == 'v'
    assert registry.models['hr.employee.public'].objects.count() >= 0


def test_a_second_init_keeps_the_view(env):
    """``CREATE OR REPLACE``: volver a llamar ``init`` no cambia el estado."""
    _drop_view()
    model = Registry(connection.alias).models['hr.employee.public']
    model.init(using=connection.alias)
    model.init(using=connection.alias)
    assert _relkind(VIEW) == 'v'


def test_init_replaces_a_view_with_another_column_set(env):
    """≙ ``tools.drop_view_if_exists`` antes del ``CREATE or REPLACE``
    (``odoo19c: addons/hr/models/hr_employee_public.py:196``): una vista
    previa con otras columnas no admite ``REPLACE``, así que se retira."""
    _drop_view()
    with connection.cursor() as cr:
        cr.execute(f'CREATE VIEW {VIEW} AS SELECT 1 AS legacy_column')
    Registry(connection.alias).models['hr.employee.public'].init(
        using=connection.alias)
    with connection.cursor() as cr:
        cr.execute("SELECT count(*) FROM information_schema.columns "
                   "WHERE table_name = %s AND column_name = 'legacy_column'",
                   [VIEW])
        assert cr.fetchone()[0] == 0
    assert _relkind(VIEW) == 'v'
