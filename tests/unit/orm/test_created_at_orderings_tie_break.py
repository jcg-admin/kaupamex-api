"""Cada orden por ``create_date`` sigue el contrato que su fuente declara.

Las fechas de ``TimeStampedModel`` son la hora de la transacción
(``cr.now()``, ``odoo19c@abe4040ec1: odoo/orm/models.py:4394-4396`` y
``:4801-4805``; ``odoo/sql_db.py:271-278``): las filas escritas en una misma
transacción comparten ``create_date``. Qué hace cada consulta con ese empate
no se decide en bloque: se deriva, consulta por consulta, de su fuente.

La clase de cada consulta, y su fuente, viven en el catálogo del Workbench
(``contracts/created-at-orderings.tsv``). Tres clases:

``reference-id``
    El modelo de la referencia desempata su ``_order`` por ``id`` en el
    mismo sentido (``'..., id desc'``). El puerto desempata igual.
``reference-untied``
    La referencia ordena por la fecha **sin** desempate; el puerto conserva
    esa forma literal y no inventa uno.
``consumer``
    Sin contraparte 1:1 en la referencia: el orden es contrato propio del
    Consumer, y el desempate por ``id`` lo hace determinista para la
    paginación de la interfaz.

*Métrica:* llamadas ``order_by`` cuyos argumentos literales incluyen
``create_date`` o ``-create_date``, en ``src/`` y ``addons/`` sin pruebas ni
migraciones, identificadas por archivo y función contenedora.
*Ciega a:* órdenes construidos con variables, ``Meta.ordering`` y
``F('create_date')``; y al orden **principal** de cada consulta, que en varias
diverge del ``_order`` de la referencia y es otra obligación.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATE = {'create_date', '-create_date'}
TIE = {'id', '-id', 'pk', '-pk'}

#: El catálogo vive en el Workbench de la iniciativa, con la revisión de
#: referencia de la que se derivó cada clase: es la autoridad única. Esta
#: prueba sólo verifica que el código de Kaupamex lo cumple.
CATALOG = (ROOT / 'scripts/workbench/orm-continuation-plan-20261103T095630'
           / 'contracts/created-at-orderings.tsv')
CLASSES = {'reference-id', 'reference-untied', 'consumer'}


def _catalog():
    rows = {}
    for line in CATALOG.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#') or line.startswith('call\t'):
            continue
        call, cls, source = line.split('\t')
        rows[call] = (cls, source)
    return rows


def _orderings():
    for base in ('src', 'addons'):
        for path in sorted((ROOT / base).rglob('*.py')):
            if {'tests', 'migrations'} & set(path.parts):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            yield from _visit(tree, [], path.relative_to(ROOT))


def _visit(node, stack, path):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            yield from _visit(child, stack + [child.name], path)
            continue
        if (isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == 'order_by'):
            keys = [a.value for a in child.args
                    if isinstance(a, ast.Constant)
                    and isinstance(a.value, str)]
            if DATE & set(keys):
                yield f"{path}::{'.'.join(stack)}", keys
        yield from _visit(child, stack, path)


def _conforms(cls, keys):
    tie = [key for key in keys if key in TIE]
    if cls == 'reference-untied':
        return not tie
    date = next(key for key in keys if key in DATE)
    return bool(tie) and tie[-1].startswith('-') == date.startswith('-')


def test_the_scan_sees_the_orderings():
    """Control: el recorrido encuentra órdenes por ``create_date``; un cero
    aquí sería un instrumento ciego, no un árbol sano."""
    assert len(list(_orderings())) >= 20


def test_the_catalog_is_well_formed():
    rows = _catalog()
    assert rows
    assert {cls for cls, __ in rows.values()} <= CLASSES
    assert all(source for __, source in rows.values())


def test_every_ordering_is_classified_in_the_catalog():
    unclassified = sorted(
        {where for where, __ in _orderings()} - set(_catalog()))
    assert unclassified == []


def test_the_catalog_has_no_stale_entries():
    assert sorted(set(_catalog()) - {w for w, __ in _orderings()}) == []


def test_every_ordering_follows_its_class():
    catalog = _catalog()
    wrong = [(where, keys) for where, keys in _orderings()
             if not _conforms(catalog[where][0], keys)]
    assert wrong == []
