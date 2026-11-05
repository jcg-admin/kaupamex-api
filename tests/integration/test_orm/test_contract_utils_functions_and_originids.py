"""Contrato de ``check_object_name``, ``check_pg_name``, ``parse_field_expr``,
``expand_ids`` y ``OriginIds`` — ``odoo19c: odoo/orm/utils.py:76-146``.

Oráculo diferencial: se ejecuta el ``utils.py`` de la referencia y se compara
con el nuestro sobre las mismas entradas. La referencia importa
``odoo.exceptions`` y ``odoo.tools``; se le dan módulos sustitutos con
nuestras ``AccessError``, ``ValidationError`` y ``SQL``, que el código sólo usa
como tipos. El módulo se compila desde su texto, sin escribir ``__pycache__``
en ``odoo-tools``. Las aserciones literales repiten lo leído del cuerpo de la
referencia y discriminan aunque el árbol no esté montado.

Mutaciones que lo hacen caer: admitir mayúsculas en ``check_object_name``;
subir el tope de ``check_pg_name`` a 64; no rechazar un campo vacío en
``parse_field_expr``; no filtrar por clase de id en ``expand_ids``; emitir los
``NewId`` sin origen en ``OriginIds.__iter__``.
"""
import contextlib
import pathlib
import sys
import types

import pytest

import exceptions
import reference_roots
from orm import utils
from orm.identifiers import NewId
from tools import sql

pytestmark = pytest.mark.integration

REFERENCE_FILE = (reference_roots.tree('odoo19c')
                  / 'odoo' / 'orm' / 'utils.py')

OBJECT_NAMES = ('res.partner', 'res_partner', 'Res.Partner', 'a-b', '',
                'x1.y2')
PG_NAMES = ('res_partner', '_x', '1abc', 'a$b', 'a-b', 'A' * 63, 'a' * 64, '')
FIELD_EXPRS = ('name', 'props.color', '.color', 'a.b.c', '', 'a.')
ID_SEQUENCES = (
    (1, [2, 1, 3, 2]),
    (NewId(), [1, NewId(origin=4), 2]),
    (5, []),
)


@contextlib.contextmanager
def _reference_package_shims():
    """``odoo.exceptions`` y ``odoo.tools`` mientras dura la ejecución."""
    package_shim = types.ModuleType('odoo')
    exceptions_shim = types.ModuleType('odoo.exceptions')
    exceptions_shim.AccessError = exceptions.AccessError
    exceptions_shim.ValidationError = exceptions.ValidationError
    tools_shim = types.ModuleType('odoo.tools')
    tools_shim.SQL = sql.SQL
    shims = {'odoo': package_shim, 'odoo.exceptions': exceptions_shim,
             'odoo.tools': tools_shim}
    saved = {name: sys.modules.get(name) for name in shims}
    sys.modules.update(shims)
    try:
        yield
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _reference_utils():
    source = pathlib.Path(REFERENCE_FILE).read_text()
    module = types.ModuleType('reference_orm_utils')
    with _reference_package_shims():
        exec(compile(source, str(REFERENCE_FILE), 'exec'), module.__dict__)
    return module


def _outcome(call):
    try:
        return ('ok', call())
    except Exception as error:
        return ('raise', type(error).__name__)


def _behaviour(module):
    rows = []
    rows += [('object', n, _outcome(lambda: module.check_object_name(n)))
             for n in OBJECT_NAMES]
    rows += [('pg', n, _outcome(lambda: module.check_pg_name(n)))
             for n in PG_NAMES]
    rows += [('expr', e, _outcome(lambda: module.parse_field_expr(e)))
             for e in FIELD_EXPRS]
    for first, rest in ID_SEQUENCES:
        rows.append(('expand', repr(first), repr(rest),
                     [repr(i) for i in module.expand_ids(first, rest)]))
    ids = (1, NewId(), NewId(origin=7), 2, NewId(ref='r'))
    origin = module.OriginIds(ids)
    rows.append(('origin_iter', list(origin)))
    rows.append(('origin_reversed', list(reversed(origin))))
    rows.append(('origin_twice', list(origin) == list(origin)))
    return rows


@pytest.mark.skipif(
    not REFERENCE_FILE.is_file(),
    reason=f'referencia ausente: {REFERENCE_FILE} no existe (odoo-tools no '
           'montado; ver referencia-odoo-gobierna-las-decisiones.md)')
class TestUtilsBehaveLikeTheReference:

    def test_every_input_matches_the_reference_module(self):
        expected = _behaviour(_reference_utils())
        observed = _behaviour(utils)
        mismatches = [(e, o) for e, o in zip(expected, observed) if e != o]
        assert len(expected) == len(observed)
        assert not mismatches, mismatches[:5]

    def test_the_shims_are_withdrawn(self):
        _reference_utils()
        assert 'odoo.exceptions' not in sys.modules


class TestUtilsLiteralContract:

    def test_object_names_are_lowercase_dotted(self):
        assert utils.check_object_name('res.partner')
        assert not utils.check_object_name('Res.Partner')

    def test_pg_names_are_capped_at_63(self):
        assert utils.check_pg_name('A' * 63) is None
        with pytest.raises(exceptions.ValidationError):
            utils.check_pg_name('a' * 64)

    def test_a_field_expression_needs_a_field(self):
        assert utils.parse_field_expr('props.color') == ('props', 'color')
        with pytest.raises(ValueError):
            utils.parse_field_expr('.color')

    def test_expand_ids_keeps_the_kind_of_the_first(self):
        assert list(utils.expand_ids(1, [2, 1, NewId(), 3])) == [1, 2, 3]

    def test_origin_ids_skip_new_ids_without_origin(self):
        ids = (1, NewId(), NewId(origin=7), 2)
        assert list(utils.OriginIds(ids)) == [1, 7, 2]
        assert list(reversed(utils.OriginIds(ids))) == [2, 7, 1]

    def test_origin_ids_has_only_the_ids_slot(self):
        with pytest.raises(AttributeError):
            utils.OriginIds(()).extra = 1
