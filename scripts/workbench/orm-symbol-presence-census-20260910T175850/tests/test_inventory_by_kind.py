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
class Field:
    type = 'base'
    store = True

    def setup(self, model):
        return model

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


def _rows(tmp_path, monkeypatch):
    reference, ours = tmp_path / 'ref', tmp_path / 'ours'
    reference.mkdir(), ours.mkdir()
    (reference / 'fields.py').write_text(REFERENCE)
    (reference / 'missing.py').write_text('def lost():\n    return 1\n')
    (ours / 'fields.py').write_text(OURS)
    monkeypatch.setattr(inv._census, 'MIRRORED_ROOTS', (('x', ours, reference),))
    return {(r[1].split('/')[-1], r[2], r[3]): r[4]
            for r in inv.inventory(('x',), 'rev')}


def test_each_kind_is_classified(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Field.setup', 'method')] == 'satisfied'
    assert rows[('fields.py', 'Field.convert', 'method')] == 'divergent'
    assert rows[('fields.py', 'Field.column', 'property')] == 'divergent'
    assert rows[('fields.py', 'Field.type', 'attribute')] == 'satisfied'
    assert rows[('fields.py', 'Field.store', 'attribute')] == 'divergent'
    assert rows[('fields.py', 'helper', 'function')] == 'satisfied'
    assert rows[('missing.py', 'lost', 'function')] == 'absent'
    assert rows[('missing.py', '', 'file')] == 'absent'
    assert rows[('fields.py', '', 'file')] == 'divergent'


def test_a_homonym_under_another_owner_is_not_verified(tmp_path, monkeypatch):
    # Una funcion de modulo ``stamp`` no es el porte de ``Field.stamp``.
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Field.stamp', 'method')] == 'not_verified'


def test_an_absent_owner_makes_its_methods_absent(tmp_path, monkeypatch):
    # ``Other.run`` no es el porte de ``Gone.run``: el nombre no es la identidad.
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Gone', 'class')] == 'absent'
    assert rows[('fields.py', 'Gone.run', 'method')] == 'absent'


def test_categories_are_exclusive_and_sum(tmp_path, monkeypatch):
    rows = _rows(tmp_path, monkeypatch)
    counts = inv.table([('rev', m, q, k, c, '') for (m, q, k), c in rows.items()])
    for kind in inv.KINDS:
        assert set(counts[kind]) <= set(inv.CATEGORIES)


def test_a_dissolved_method_is_divergent_not_absent(tmp_path, monkeypatch):
    # El arbol disuelve metodos de ``Field`` en funciones ``_field_*``: el
    # simbolo existe con otro mecanismo, no falta.
    rows = _rows(tmp_path, monkeypatch)
    assert rows[('fields.py', 'Field.resolve_depends', 'method')] == 'divergent'
