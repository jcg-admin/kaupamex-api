"""Control del inventario por tipo: categorias excluyentes y su invariante.

Los sujetos son dos archivos sinteticos —referencia y espejo— porque lo que
se defiende es la REGLA de clasificacion, no un conteo del arbol: un control
sobre el arbol cambia con cada porte y dejaria de discriminar.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import inventory_by_kind as inv  # noqa: E402

REFERENCE = '''
import typing


class Field:
    type = 'base'
    store = True

    def setup(self, model):
        return model

    @typing.overload
    def convert(self, value: int, record) -> int: ...

    def convert(self, value, record):
        return value

    @property
    def column(self):
        return 1

    def stamp(self):
        return 2

    def resolve_depends(self):
        return ()


class Gone:
    def run(self):
        return 1


def helper(a, b=1):
    return a
'''

OURS = '''
class Field:
    type = 'base'
    store = False

    def setup(self, model):
        return model

    def convert(self, value):
        return value

    @property
    def column(self):
        pass


class Other:
    def run(self):
        return 1


def helper(a, b=1):
    return a


def stamp():
    return 2


def _field_resolve_depends(field):
    return ()
'''


def _rows(tmp_path, monkeypatch, known=frozenset(), evidence=None):
    reference, ours = tmp_path / 'ref', tmp_path / 'ours'
    reference.mkdir(parents=True), ours.mkdir(parents=True)
    (reference / 'fields.py').write_text(REFERENCE)
    (reference / 'missing.py').write_text('def lost():\n    return 1\n')
    (ours / 'fields.py').write_text(OURS)
    monkeypatch.setattr(inv._census, 'MIRRORED_ROOTS', (('x', ours, reference),))
    rows = inv.inventory(('x',), 'rev', known=set(known), evidence=evidence or {})
    return {(r[1].split('/')[-1], r[2], r[3]): r[4] for r in rows}


def test_a_structural_match_without_evidence_is_not_verified(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Field.setup', 'method')] == 'not_verified'
    assert rows[('fields.py', 'helper', 'function')] == 'not_verified'
    assert rows[('fields.py', 'Field.type', 'attribute')] == 'not_verified'


def test_a_structural_match_with_evidence_is_satisfied(tmp_path, monkeypatch):
    evidence = {('x/fields.py', 'Field.setup', 'method'): 'tests/x.py::case'}
    rows = _rows(tmp_path, monkeypatch, evidence=evidence)
    assert rows[('fields.py', 'Field.setup', 'method')] == 'satisfied'


def test_evidence_does_not_cover_a_different_signature(tmp_path, monkeypatch):
    evidence = {('x/fields.py', 'Field.convert', 'method'): 'tests/x.py::case'}
    rows = _rows(tmp_path, monkeypatch, evidence=evidence)
    assert rows[('fields.py', 'Field.convert', 'method')] == 'not_verified'


def test_an_empty_body_where_the_reference_implements_is_divergent(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Field.column', 'property')] == 'divergent'


def test_absent_requires_the_name_to_be_unknown_to_the_whole_consumer(tmp_path, monkeypatch):
    unknown = _rows(tmp_path / 'a', monkeypatch)
    assert unknown[('missing.py', 'lost', 'function')] == 'absent'
    known = _rows(tmp_path / 'b', monkeypatch, known={'lost'})
    assert known[('missing.py', 'lost', 'function')] == 'not_verified'


def test_a_homonym_under_another_owner_is_not_verified(tmp_path, monkeypatch):
    # Una funcion de modulo ``stamp`` no es el porte de ``Field.stamp``.
    rows = _rows(tmp_path, monkeypatch, known={'stamp'})
    assert rows[('fields.py', 'Field.stamp', 'method')] == 'not_verified'


def test_a_dissolved_method_is_not_verified_not_absent(tmp_path, monkeypatch):
    # Disuelto en ``_field_resolve_depends``: existe con otro mecanismo.
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Field.resolve_depends', 'method')] == 'not_verified'


def test_categories_are_exclusive_and_sum(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    counts = inv.table([('rev', m, q, k, c, '') for (m, q, k), c in rows.items()])
    for kind in inv.KINDS:
        assert set(counts[kind]) <= set(inv.CATEGORIES)


def test_a_typing_overload_is_not_another_obligation(tmp_path, monkeypatch):
    reference = tmp_path / 'ref' / 'fields.py'
    rows = _rows(tmp_path, monkeypatch)
    assert [k for k in rows if k[1] == 'Field.convert'] == [('fields.py', 'Field.convert', 'method')]
    assert sum(1 for r in inv.typed_symbols(reference) if r['name'] == 'convert') == 1


def test_a_property_with_a_setter_is_one_obligation(tmp_path):
    source = tmp_path / 'lru.py'
    source.write_text(
        'class LRU:\n'
        '    @property\n'
        '    def count(self):\n'
        '        return 1\n'
        '\n'
        '    @count.setter\n'
        '    def count(self, value):\n'
        '        pass\n'
        '\n'
        '    @count.deleter\n'
        '    def count(self):\n'
        '        pass\n')
    records = [r for r in inv.typed_symbols(source) if r['name'] == 'count']
    assert [r['kind'] for r in records] == ['property']


INSTALLING = '''
from django.db import models

DEFAULTS = {'help': None, 'groups': None}

for _name, _value in DEFAULTS.items():
    if not hasattr(models.Field, _name):
        setattr(models.Field, _name, _value)

models.Field.copy = True
setattr(models.Field, 'exportable', True)

for _key, _source in (('string', 'string'), ('help', 'help')):
    setattr(models.Field, f'_related_{_key}', property(lambda f: f))


class Holder:
    def __init__(self):
        self.secret = 1


def touch(record):
    record.local_only = 2
'''


def test_a_name_installed_on_another_class_is_known(tmp_path):
    """H-API-1167: el puerto instala atributos en ``models.Field`` por
    asignación, por ``setattr`` con nombre literal y por bucle sobre las
    claves de un diccionario. Ninguno es una ``def`` ni una ``class``, y el
    censo los contaba como ausentes. Un ``self.x`` es estado de instancia,
    no una instalación, y no cuenta."""
    path = tmp_path / 'installing.py'
    path.write_text(INSTALLING)
    names = inv.installed_names(path)
    assert {'help', 'groups', 'copy', 'exportable'} <= names
    assert {'Field.help', 'Field.groups', 'Field.copy',
            'Field.exportable'} <= names
    assert {'Field._related_string', 'Field._related_help'} <= names
    assert 'secret' not in names
    assert 'local_only' not in names


def test_an_attribute_installed_on_its_class_is_not_absent(
        tmp_path, monkeypatch):
    """El atributo de clase ``Field.store`` de la referencia no tiene
    ``class Field`` en el espejo cuando el puerto lo instala en la clase de
    Django: conocido como ``Field.store``, pasa de ``absent`` a
    ``not_verified`` —presencia, no contrato—."""
    reference, ours = tmp_path / 'ref', tmp_path / 'ours'
    reference.mkdir(parents=True), ours.mkdir(parents=True)
    (reference / 'fields.py').write_text('class Field:\n    store = True\n')
    (ours / 'fields.py').write_text('X = 1\n')
    monkeypatch.setattr(inv._census, 'MIRRORED_ROOTS',
                        (('x', ours, reference),))

    def category(known):
        rows = inv.inventory(('x',), 'rev', known=known, evidence={})
        return next(r[4] for r in rows if r[2] == 'Field.store')

    assert category(set()) == 'absent'
    assert category({'Field.store'}) == 'not_verified'


def test_an_attribute_installed_in_a_loop_over_port_classes_is_located(
        tmp_path, monkeypatch):
    """H-API-1177: ``_Relational`` es una base abstracta de la referencia
    que el puerto no tiene; sus atributos se instalan en un bucle sobre las
    clases de campo del puerto. El dueño que el censo ve es la variable del
    bucle, nunca ``_Relational``, y la implementación localizada salía
    ``absent``. Instalada en el propio espejo, es presencia en otra clase:
    ``not_verified`` con ``installed_elsewhere``, nunca ``satisfied`` sin
    coincidencia estructural."""
    reference, ours = tmp_path / 'ref', tmp_path / 'ours'
    reference.mkdir(parents=True), ours.mkdir(parents=True)
    (reference / 'fields_relational.py').write_text(
        'class _Relational:\n    context = {}\n    domain = []\n')
    (ours / 'fields_relational.py').write_text(
        'class A:\n    pass\n\n\nclass B:\n    pass\n\n\n'
        'for _cls in (A, B):\n    _cls.context = property(lambda s: {})\n')
    monkeypatch.setattr(inv._census, 'MIRRORED_ROOTS',
                        (('x', ours, reference),))
    rows = {r[2]: (r[4], r[5]) for r in inv.inventory(
        ('x',), 'rev', known=set(),
        evidence={('x/fields_relational.py', '_Relational.context',
                   'attribute'): 'case'})}
    category, reason = rows['_Relational.context']
    assert category == 'not_verified'
    assert 'structural=installed_elsewhere' in reason
    assert rows['_Relational.domain'][0] == 'absent'
