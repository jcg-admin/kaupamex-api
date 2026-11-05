"""``tools.json`` medido contra la fuente ejecutada.

Se carga ``odoo19c: odoo/tools/json.py`` por ruta y se comparan ``JSON``,
``_ScriptSafe`` y ``stringify_keys`` con los nuestros. La fuente importa
``.func`` y ``.misc`` de forma relativa: ``.func`` es la ``func.py`` **de la
referencia**, que sólo usa la biblioteca estándar; ``.misc`` es un sustituto
que expone el ``ReadonlyDict`` **del puerto**, porque el ``misc`` de la
referencia arrastra media plataforma. Los dos se retiran tras la carga.

``json_default`` no entra: importa ``odoo.fields`` en cada llamada, y su
evidencia ya vive en ``tests/unit/tools/test_json_default.py``.

*Métrica:* el valor devuelto —o el nombre de la excepción— de ``loads``,
``dumps``, ``__html__`` y ``stringify_keys`` sobre una rejilla de cargas con
los cinco caracteres que el escape protege.
*Ciega a:* ``ReadonlyDict`` (los dos lados usan el del puerto) y a toda
divergencia que la fuente comparta con nosotros.
"""
import importlib.util
import pathlib
import sys
import types
from collections import OrderedDict

import markupsafe
import pytest

from tools import json as ported
from tools import misc as ported_misc

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_json', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

PACKAGE = 'reference_tools_package'
UNSAFE = '</script><b>&amp;\u2028\u2029'
PAYLOADS = (
    None, 1, 2.5, 'plain', UNSAFE, ['a', UNSAFE, {'k': '<'}],
    {'html': UNSAFE, 'n': [1, 2], 'nested': {'x': '&'}},
    {'b': 1, 'a': 2},
)
MAPPINGS = (
    {1: 'a', (2, 3): {4: 'b'}},
    OrderedDict([(None, [{5: 'c'}]), ('k', 'v')]),
    [{1: 2}],
    'not a mapping',
    {'already': {'strings': 1}},
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reference_module():
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:
        return None
    tools = root / 'odoo' / 'tools'
    if not (tools / 'json.py').is_file():
        return None
    package = types.ModuleType(PACKAGE)
    package.__path__ = []
    misc = types.ModuleType(f'{PACKAGE}.misc')
    misc.ReadonlyDict = ported_misc.ReadonlyDict
    sys.modules.update({PACKAGE: package, f'{PACKAGE}.misc': misc})
    try:
        load(f'{PACKAGE}.func', tools / 'func.py')
        return load(f'{PACKAGE}.json', tools / 'json.py')
    finally:
        for name in [n for n in sys.modules if n.split('.')[0] == PACKAGE]:
            del sys.modules[name]


@pytest.fixture(scope='module')
def reference():
    module = reference_module()
    if module is None:
        pytest.skip('la referencia no está montada en esta sesión')
    return module


def outcome(call):
    try:
        value = call()
    except Exception as error:
        return ('raises', type(error).__name__)
    return ('value', type(value).__name__, value)


def calls(module):
    grid = []
    for payload in PAYLOADS:
        grid += [
            (f'dumps({payload!r})',
             lambda p=payload: module.scriptsafe.dumps(p)),
            (f'dumps({payload!r}, sort_keys)',
             lambda p=payload: module.scriptsafe.dumps(p, sort_keys=True)),
            (f'dumps({payload!r}).__html__()',
             lambda p=payload: module.scriptsafe.dumps(p).__html__()),
            (f'loads(dumps({payload!r}))',
             lambda p=payload: module.scriptsafe.loads(
                 module.scriptsafe.dumps(p))),
        ]
    for mapping in MAPPINGS:
        grid.append((f'stringify_keys({mapping!r})',
                     lambda m=mapping: module.stringify_keys(m)))
    grid += [
        ('loads(invalid)', lambda: module.scriptsafe.loads('{bad')),
        ('dumps(set)', lambda: module.scriptsafe.dumps({1, 2})),
        ('html of a bare string',
         lambda: module._ScriptSafe(UNSAFE).__html__()),
    ]
    return grid


class TestJsonBehavesLikeTheReference:

    def test_every_call_returns_what_the_reference_returns(self, reference):
        theirs, ours = calls(reference), calls(ported)
        divergences = [
            (label, outcome(their_call), outcome(our_call))
            for (label, their_call), (_label, our_call) in zip(theirs, ours)
            if outcome(their_call) != outcome(our_call)]
        assert len(theirs) >= 40
        assert not divergences, divergences[:3]

    def test_the_classes_have_the_reference_shape(self, reference):
        assert ported._ScriptSafe.__mro__[1] is str
        assert reference._ScriptSafe.__mro__[1] is str
        mapper = reference.JSON_SCRIPTSAFE_MAPPER
        assert ported.JSON_SCRIPTSAFE_MAPPER == mapper
        assert isinstance(ported.scriptsafe, ported.JSON)


class TestJsonLiterally:
    """Casos escritos a mano: el diferencial no dice cuál se rompió."""

    def test_the_html_form_escapes_the_script_terminator(self):
        html = ported.scriptsafe.dumps('</script>').__html__()
        assert isinstance(html, markupsafe.Markup)
        assert '</script>' not in html
        assert '\\u003c/script\\u003e' in html

    def test_the_serialized_text_is_unchanged_before_html(self):
        assert ported.scriptsafe.dumps('<') == '"<"'

    def test_mapping_keys_become_strings_recursively(self):
        assert ported.stringify_keys({1: {2: 'x'}}) == {'1': {'2': 'x'}}
