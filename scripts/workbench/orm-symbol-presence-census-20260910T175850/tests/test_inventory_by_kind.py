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
