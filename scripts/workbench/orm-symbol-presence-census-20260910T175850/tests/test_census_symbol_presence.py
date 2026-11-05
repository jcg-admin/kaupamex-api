"""Control del censo de PRESENCIA con firma — TDD, la mitad ROJA primero.

Lo que discrimina no es «cuenta simbolos»: los cinco instrumentos que ya
existen cuentan. Lo que ninguno mide es si el simbolo presente tiene CUERPO,
y ese criterio de cierre —«0 ausentes»— lo satisface un arbol de firmas
vacias. Asi que la columna que este control tiene que defender es ``stub``.

Los sujetos son REALES y del arbol, no fabricados: un caso inventado por quien
escribio el detector hereda su encuadre y confirma su propia lectura.
"""
import ast
import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
_census = importlib.import_module('census_symbol_presence')
body_class = _census.body_class
signature_of = _census.signature_of
declared_symbols = _census.declared_symbols
REPO = _census.REPO

sys.path.insert(0, str(REPO / 'scripts'))
reference_roots = importlib.import_module('reference_roots')


def _symbol(relative_path, name):
    """El registro de un simbolo real del arbol, por nombre."""
    found = [s for s in declared_symbols(REPO / relative_path)
             if s['name'] == name]
    assert found, (
        f'{name} ya no existe en {relative_path}: el control perdio su sujeto')
    return found[0]


# --- la columna que discrimina: stub vs sustantivo -------------------------

def test_a_pass_only_body_is_a_stub():
    # src/orm/registry.py — el cerrojo nulo: `def acquire(self): pass`
    assert _symbol('src/orm/registry.py', 'acquire')['body'] == 'stub'


def test_a_docstring_only_body_is_a_stub():
    # src/orm/fields.py — «Verbatim: la fuente no hace nada aqui»
    record = _symbol('src/orm/fields.py', '_field_setup_nonrelated')
    assert record['body'] == 'stub'


def test_a_bare_not_implemented_body_is_a_stub():
    # src/orm/domains.py — `def __eq__(self): raise NotImplementedError`
    assert _symbol('src/orm/domains.py', '__eq__')['body'] == 'stub'


def test_a_conditional_not_implemented_is_substantive():
    # EL QUE DISCRIMINA. src/orm/decorators.py `depends` levanta
    # NotImplementedError DENTRO de un `elif`: un detector por subcadena lo
    # llamaria stub y borraria de la medicion una guarda con logica real.
    assert _symbol('src/orm/decorators.py', 'depends')['body'] == 'substantive'


def test_a_super_only_body_is_substantive():
    # src/orm/registry.py — `super().__init__('_constrains')`. Delegar NO es
    # no hacer nada: el argumento es la decision que el cuerpo toma. El sujeto
    # se localiza por su texto, no por su linea: anclado a la 844 dejo de
    # existir en cuanto el archivo crecio.
    path = REPO / 'src/orm/registry.py'
    line = next(n for n, text in enumerate(path.read_text().splitlines(), 1)
                if "super().__init__('_constrains')" in text)
    delegating = [s for s in declared_symbols(path)
                  if s['name'] == '__init__' and s['lineno'] == line - 1]
    assert delegating, 'el __init__ delegante de registry.py ya no existe'
    assert delegating[0]['body'] == 'substantive'


# --- el otro eje nuevo: la firma ------------------------------------------

def test_signature_drops_the_receiver():
    # `self` / `cls` no son parte del contrato: comparar con ellos haria que un
    # metodo y su equivalente de modulo nunca casaran.
    sig = _symbol('src/orm/registry.py', 'acquire')['signature']
    assert sig['params'] == []


def test_signature_records_defaults_as_flags_not_values():
    # El VALOR del default es cuerpo; lo que el contrato declara es que el
    # parametro es opcional. Guardar el valor haria fallar el emparejamiento
    # ante una constante renombrada.
    source = 'def probe(a, b=1, *rest, key=None, **extra): pass'
    node = ast.parse(source).body[0]
    sig = signature_of(node)
    assert sig['params'] == ['a', 'b']
    assert sig['has_default'] == [False, True]
    assert sig['vararg'] == 'rest'
    assert sig['kwonly'] == ['key']
    assert sig['kwarg'] == 'extra'


def test_body_class_is_computed_from_the_node_not_the_text():
    stub = ast.parse('def f():\n    """doc."""\n').body[0]
    assert body_class(stub) == 'stub'
    live = ast.parse('def f():\n    return 1\n').body[0]
    assert body_class(live) == 'substantive'


# --- definiciones condicionales: el punto ciego de ``deprecated`` ---------

def test_a_symbol_defined_inside_a_module_try_is_declared():
    # src/orm/decorators.py: ``try: from warnings import deprecated`` /
    # ``except ImportError: class deprecated``. La clase y sus metodos estan
    # bajo el ``except``; leer solo el cuerpo del modulo no los veia.
    records = declared_symbols(REPO / 'src/orm/decorators.py')
    names = {(r['owner'], r['name'], r['kind']) for r in records}
    assert (None, 'deprecated', 'class') in names
    assert ('deprecated', '__call__', 'method') in names


def test_a_symbol_defined_inside_a_module_if_is_declared():
    # src/tools/mail.py:
    # ``if hasattr(email.utils, 'supports_strict_parsing')``.
    names = {r['name'] for r in declared_symbols(REPO / 'src/tools/mail.py')}
    assert 'getaddresses' in names


def test_typing_only_and_script_blocks_are_not_contract():
    # Lo que vive bajo ``if TYPE_CHECKING`` no existe al ejecutar, y lo de
    # ``if __name__ == '__main__'`` es un guion, no superficie importable.
    root = pathlib.Path(reference_roots.tree('odoo19c'))
    typing_only = {r['name'] for r in declared_symbols(
        root / 'odoo/tools/babel/javascript_extractor.py')}
    script = {r['name'] for r in declared_symbols(
        root / 'odoo/tools/float_utils.py')}
    assert '_FileObj' not in typing_only
    assert 'try_round' not in script

