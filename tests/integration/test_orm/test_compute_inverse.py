"""Compute, inverse y restricción en ``create``/``write`` — porte de
``test_15_constraint_inverse``, del bloque ``test_orm.compute.inverse`` de
``test_inverse`` y de ``test_x2many_computed_inverse``.

Referencia: odoo-tools ``abe4040ec1``,
``odoo19c: odoo/addons/test_orm/tests/test_fields.py:649-675``,
``:822-843`` y ``:4856-4868`` sobre ``test_orm.compute.inverse``
(``…/models/test_orm.py:543-584``). El flujo que fijan: un ``write`` valida
primero los campos que no se invierten (``odoo19c: odoo/orm/models.py:4490-
4491``), despacha los inversos y valida después los invertidos (``:4514``).

Las aserciones de SQL de la fuente —el ``assertQueries`` de ``test_inverse``
(``:676-679``) y ``test_compute_inverse`` entero (``:4826-4854``)— se portan
como cobertura PENDIENTE: ``xfail(strict=True)`` con su dependencia,
TASK-API-0510 (``_write``/``_write_multi``/``_flush``). Corren, hoy fallan, y
un paso inesperado lo delata. No se declaran satisfechas.

``env['x']`` devuelve aquí la clase del modelo (divergencia declarada en
``Environment.__getitem__``); el recordset vacío que la fuente obtiene así se
escribe ``env['x'].browse(())``, y sobre él ``with_context`` es el de la
fuente.
"""
import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

PENDING_WRITE_MULTI = pytest.mark.xfail(
    strict=True,
    reason='TASK-API-0510: INSERT/UPDATE por lote de _write_multi/_flush; '
           'aquí la escritura es por fila')


def insert(model, *fnames, rowcount=1):
    """≙ ``insert`` (``test_fields.py:4747-4752``), con las columnas de
    registro de este árbol (``create_date``/``write_date``)."""
    columns = sorted(fnames + ('create_date', 'write_date'))
    header = ", ".join(f'"{column}"' for column in columns)
    template = ", ".join("%s" for _index in range(rowcount))
    return (f'INSERT INTO "{model._meta.db_table}" ({header}) '
            f'VALUES {template} RETURNING "id"')


def update(model, *fnames):
    """≙ ``update`` (``test_fields.py:4755-4768``)."""
    table = f'"{model._meta.db_table}"'
    fnames = sorted(fnames + ('write_date',))
    columns = ", ".join(f'"{column}"' for column in fnames)
    assignments = ", ".join(
        f'"{fname}" = "__tmp"."{fname}"' for fname in fnames)
    return (f'UPDATE {table} SET {assignments} '
            f'FROM (VALUES %s) AS "__tmp"("id", {columns}) '
            f'WHERE {table}."id" = "__tmp"."id"')


def assert_queries(expected, captured):
    """≙ ``assertQueries``: las sentencias emitidas, en orden."""
    assert [query['sql'] for query in captured.captured_queries] == expected


pytestmark = pytest.mark.django_db


def test_compute_inverse_logs(env):
    """≙ ``test_inverse``, bloque de ``test_orm.compute.inverse``."""
    # create/write on 'foo' should only invoke the compute method
    log = []
    model = env['test_orm.compute.inverse'].browse(()).with_context(log=log)
    record = model.create({'foo': 'Hi'})
    assert record.foo == 'Hi'
    assert record.bar == 'Hi'
    assert sorted(log) == ['compute']

    log.clear()
    record.write({'foo': 'Ho'})
    assert record.foo == 'Ho'
    assert record.bar == 'Ho'
    assert sorted(log) == ['compute']

    # create/write on 'bar' should only invoke the inverse method
    log.clear()
    record = model.create({'bar': 'Hi'})
    assert record.foo == 'Hi'
    assert record.bar == 'Hi'
    assert sorted(log) == ['inverse']

    log.clear()
    record.write({'bar': 'Ho'})
    assert record.foo == 'Ho'
    assert record.bar == 'Ho'
    assert sorted(log) == ['inverse']


def test_15_constraint_inverse(env):
    """ test constraint method on normal field and field with inverse """
    log = []
    model = env['test_orm.compute.inverse'].browse(()).with_context(
        log=log, log_constraint=True)

    # create/write with normal field only
    log.clear()
    record = model.create({'baz': 'Hi'})
    assert sorted(log) == ['constraint']

    log.clear()
    record.write({'baz': 'Ho'})
    assert sorted(log) == ['constraint']

    # create/write with inverse field only
    log.clear()
    record = model.create({'bar': 'Hi'})
    assert sorted(log) == ['constraint', 'inverse']

    log.clear()
    record.write({'bar': 'Ho'})
    assert sorted(log) == ['constraint', 'inverse']


def test_x2many_computed_inverse(env):
    record = env['test_orm.compute.inverse'].create(
        {'child_ids': [(0, 0, {'foo': 'child'})]},
    )
    assert len(record.child_ids) == 1, (
        f"Should be a single record: {record.child_ids!r}")
    assert record.child_ids.id, (
        f"Should be database records: {record.child_ids!r}")
    assert record.foo == 'has one child'


def test_a_stored_computed_one2many_recomputes_from_its_dependency(env):
    """El ``One2many`` calculado y almacenado entra en el grafo de
    ``@api.depends``: escribir ``foo`` lo deja pendiente
    (``odoo19c: odoo/orm/models.py:4486``, ``modified(vals)``) y leerlo lo
    recalcula en la base (``fields.py:1664-1666``). Diseño:
    ``designs/stored-computed-one2many.md``."""
    model = env['test_orm.compute.inverse']
    field = model._fields['child_ids']
    record = model.create({'foo': 'none'})
    assert not record.child_ids

    record.write({'foo': 'has one child'})
    assert env.is_to_compute(field, record.id)

    children = record.child_ids
    assert not env.is_to_compute(field, record.id)
    assert len(children) == 1
    assert children.foo == 'child'
    stored = model.search([('parent_id', '=', record.id)])
    assert stored.ids == children.ids


@PENDING_WRITE_MULTI
def test_inverse_multiple_compute_inverse_queries(env):
    """≙ ``test_inverse`` ``:676-679``: crear con ``foo`` y ``bar`` emite un
    solo ``INSERT`` con las dos columnas."""
    model = env['test_orm.compute.inverse']
    with CaptureQueriesContext(connection) as captured:
        record = model.create({'foo': 'Foo', 'bar': 'Bar'})
    assert record.bar == 'Bar'
    assert_queries([insert(model, 'foo', 'bar')], captured)


@PENDING_WRITE_MULTI
def test_compute_inverse(env):
    """≙ ``test_compute_inverse`` (``:4826-4854``): con y sin valor, con y
    sin ``default_bar``, el ``INSERT`` lleva lo dado y el inverso se vuelca
    en un ``UPDATE`` aparte."""
    model = env['test_orm.compute.inverse']
    model.create({})

    # no value, no default
    with CaptureQueriesContext(connection) as captured:
        record = model.create({'foo': 'Foo'})
    assert_queries([insert(model, 'foo'), update(model, 'bar')], captured)
    assert (record.foo, record.bar) == ('Foo', 'Foo')

    # some value, no default
    with CaptureQueriesContext(connection) as captured:
        record = model.create({'foo': 'Foo', 'bar': 'Bar'})
    assert_queries([insert(model, 'foo', 'bar'), update(model, 'foo')],
                   captured)
    assert (record.foo, record.bar) == ('Bar', 'Bar')

    model = model.with_context(default_bar='Def')

    # no value, some default
    with CaptureQueriesContext(connection) as captured:
        record = model.create({'foo': 'Foo'})
    assert_queries([insert(model, 'foo', 'bar'), update(model, 'foo')],
                   captured)
    assert (record.foo, record.bar) == ('Def', 'Def')

    # some value, some default
    with CaptureQueriesContext(connection) as captured:
        record = model.create({'foo': 'Foo', 'bar': 'Bar'})
    assert_queries([insert(model, 'foo', 'bar'), update(model, 'foo')],
                   captured)
    assert (record.foo, record.bar) == ('Bar', 'Bar')


def test_compute_inverse_values_without_query_shape(env):
    """Los VALORES de ``test_compute_inverse`` sin la forma del SQL: lo que
    sí debe cumplirse hoy, independiente de TASK-API-0510."""
    model = env['test_orm.compute.inverse']
    model.create({})
    record = model.create({'foo': 'Foo'})
    assert (record.foo, record.bar) == ('Foo', 'Foo')
    record = model.create({'foo': 'Foo', 'bar': 'Bar'})
    assert (record.foo, record.bar) == ('Bar', 'Bar')
    model = model.with_context(default_bar='Def')
    record = model.create({'foo': 'Foo'})
    assert (record.foo, record.bar) == ('Def', 'Def')
    record = model.create({'foo': 'Foo', 'bar': 'Bar'})
    assert (record.foo, record.bar) == ('Bar', 'Bar')


# --- One2many calculado y almacenado ---------------------------------------

def _children_in_database(env, record):
    return env['test_orm.compute.inverse'].search(
        [('parent_id', '=', record.id)])


def test_stored_one2many_commands_are_materialised_not_kept(env):
    """La asignación de comandos se aplica en la base (≙ ``write_real``):
    el valor es un recordset de filas con id, con la FK del padre, y la
    caché de la fila no guarda la lista de comandos."""
    record = env['test_orm.compute.inverse'].create(
        {'child_ids': [(0, 0, {'foo': 'child'})]})
    children = record.child_ids
    assert children._name == 'test_orm.compute.inverse'
    assert all(isinstance(i, int) for i in children.ids)
    assert children.parent_id == record
    assert _children_in_database(env, record).ids == children.ids
    assert not any(isinstance(value, list) and value
                   and isinstance(value[0], tuple)
                   for value in record.__dict__.values())


def test_stored_one2many_survives_a_cache_clear(env):
    """Tras vaciar la caché el valor sale de la base, sin recalcular."""
    log = []
    model = env['test_orm.compute.inverse'].browse(()).with_context(log=log)
    record = model.create({'foo': 'has one child'})
    first = record.child_ids.ids
    assert len(first) == 1
    env.invalidate_all()
    log.clear()
    again = env['test_orm.compute.inverse'].browse(record.ids)
    assert again.child_ids.ids == first
    assert 'compute' not in log


def test_stored_one2many_in_batch(env):
    """Escribir la dependencia de dos registros deja pendientes a los dos;
    leer uno recalcula el lote y cada uno queda con su propio hijo."""
    model = env['test_orm.compute.inverse']
    field = model._fields['child_ids']
    records = model.create([{'foo': 'a'}, {'foo': 'b'}])
    records.write({'foo': 'has one child'})
    assert all(env.is_to_compute(field, i) for i in records.ids)
    first, second = records
    assert len(first.child_ids) == 1
    assert len(second.child_ids) == 1
    assert first.child_ids != second.child_ids
    assert second.child_ids.parent_id == second


def test_stored_one2many_rolls_back_with_its_savepoint(env, assert_raises):
    """Los hijos que escribe el cómputo viven en la transacción: un
    savepoint que se deshace los retira."""
    record = env['test_orm.compute.inverse'].create({'foo': 'none'})
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            record.write({'foo': 'has one child'})
            assert len(record.child_ids) == 1
            raise RuntimeError
    env.invalidate_all(flush=False)
    assert not _children_in_database(env, record)


def test_stored_one2many_inverse_dispatch(env):
    """Asignar el campo fuera del cómputo despacha su ``inverse``
    (``_inverse_child_ids``), que escribe ``foo``."""
    record = env['test_orm.compute.inverse'].create({'foo': 'none'})
    record.child_ids = [(0, 0, {'foo': 'child'})]
    assert record.foo == 'has one child'
    assert len(_children_in_database(env, record)) == 1


# --- One2many calculado sin almacenar --------------------------------------

def test_non_stored_one2many_is_invalidated_by_its_dependency(env):
    """``test_orm.computed_inverse_one2many``: su valor vive en la caché de
    la transacción; añadir una línea a ``all_line_ids`` lo invalida y la
    lectura siguiente recalcula."""
    model = env['test_orm.computed_inverse_one2many']
    line_model = env['test_orm.computed_inverse_one2many_line']
    record = model.create({'name': 'r'})
    assert not record.low_priority_line_ids
    line = line_model.create({'name': 'l', 'priority': 1,
                              'parent_id': record.id})
    assert record.low_priority_line_ids == line
    field = model._fields['low_priority_line_ids']
    assert record.id in field._get_cache(env)
    env.invalidate_all()
    assert record.id not in field._get_cache(env)
    assert record.low_priority_line_ids == line


# --- la familia de escritura del One2many ----------------------------------
# ≙ ``_RelationalMulti.write``/``write_batch`` y ``One2many.write_real``/
# ``write_new`` (``odoo19c: odoo/orm/fields_relational.py:737-764``,
# ``:969-1121``).

def test_field_write_persists_and_discards_the_pending_compute(env):
    model = env['test_orm.compute.inverse']
    field = model._fields['child_ids']
    record = model.create({'foo': 'x'})
    env.add_to_compute(field, [record.id])
    field.write(record, [(0, 0, {'foo': 'via write'})])
    assert not env.is_to_compute(field, record.id)
    children = _children_in_database(env, record)
    assert children.mapped('foo') == ['via write']


@pytest.mark.parametrize('shape', ['tuple', 'recordset', 'ids', 'false'])
def test_write_batch_normalises_each_value_shape(env, shape):
    model = env['test_orm.compute.inverse']
    field = model._fields['child_ids']
    record = model.create({'foo': 'x'})
    kept = model.create({'foo': 'kept', 'parent_id': record.id})
    other = model.create({'foo': 'other'})
    value = {'tuple': (other.id,), 'recordset': other,
             'ids': [other.id], 'false': False}[shape]
    field.write_batch([(record, value)])
    expected = [] if shape == 'false' else [other.id]
    assert _children_in_database(env, record).ids == expected
    assert kept.id not in _children_in_database(env, record).ids


def test_write_batch_rejects_a_value_that_is_not_a_command_list(env):
    model = env['test_orm.compute.inverse']
    record = model.create({'foo': 'x'})
    with pytest.raises(ValueError, match='Wrong value for'):
        model._fields['child_ids'].write_batch([(record, 'nope')])


def test_write_new_keeps_new_lines_in_cache_only(env):
    model = env['test_orm.compute.inverse']
    field = model._fields['child_ids']
    owner = model.new({'foo': 'n'})
    before = model.search_count([])
    field.write_batch([(owner, [(0, 0, {'foo': 'new child'})])])
    assert model.search_count([]) == before
    lines = owner.child_ids
    assert len(lines) == 1
    assert not lines.id


def test_write_batch_refuses_a_mix_of_real_and_new_records(env):
    model = env['test_orm.compute.inverse']
    field = model._fields['child_ids']
    real = model.create({'foo': 'r'})
    new = model.new({'foo': 'n'})
    with pytest.raises(AssertionError, match='mix of real and new'):
        field.write_batch([(real, [(5, 0, 0)]), (new, [(5, 0, 0)])])
