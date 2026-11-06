"""Un paquete ``odoo`` sustituto armado sólo con módulos de la referencia.

Carga, desde ``odoo19c``, los módulos que ``odoo/orm/domains.py`` importa:
``odoo.exceptions``, ``odoo.tools`` (``SQL``, ``Query``, ``classproperty`` y
tres definiciones de ``misc``), ``odoo.tools.date_utils`` y
``odoo.orm.identifiers``/``utils``. Ninguna pieza del puerto entra.

Dos sustituciones, las dos fuera del código que se compara:

- **``psycopg2``.** Dependencia original: el módulo ``psycopg2`` que
  ``odoo/tools/sql.py`` importa. Sustituto: un módulo con su única excepción
  nombrada, ``NotSupportedError``. Razón: este stack instala psycopg 3, no
  psycopg 2. Alcance: sólo ``create_index`` la captura, y ninguna prueba que
  use este paquete la ejecuta. Efecto no verificado: cualquier ruta de la
  referencia que llame a psycopg 2; si una prueba la alcanzara, fallaría con
  ``AttributeError`` sobre el sustituto, no daría un valor falso.
- **``misc.py``.** Dependencia original: ``odoo/tools/misc.py`` completo.
  Sustituto: sus definiciones ``MISC_DEFINITIONS``, extraídas por AST del
  mismo archivo, sin modificar su texto. Razón: el módulo completo importa
  media plataforma (``odoo.loglevels``, ``babel``, ``lxml``, …). Alcance:
  ``sql``, ``query`` y ``domains`` sólo usan esas cinco. Efecto no verificado:
  una definición de ``misc`` que alguna de esas cinco use por nombre global
  y que no esté en la lista; fallaría con ``NameError``, no en silencio.

Todo se registra en ``sys.modules`` durante la carga y se retira después; los
módulos cargados conservan sus referencias.
"""
import ast
import contextlib
import importlib.util
import pathlib
import sys
import types

MISC_DEFINITIONS = ('named_to_positional_printf', '_PrintfArgs', 'OrderedSet',
                    'partition', 'str2bool')
MISC_HEADER = (
    'import typing\n'
    'from collections.abc import Callable, Iterable, Mapping, MutableSet\n'
    "T = typing.TypeVar('T')\n"
)


def _defined_names(node):
    """Los nombres que declara una sentencia de nivel superior."""
    if hasattr(node, 'name'):
        return {node.name}
    targets = getattr(node, 'targets', [])
    return {target.id for target in targets if isinstance(target, ast.Name)}


def misc_definitions(path, names=MISC_DEFINITIONS, header=MISC_HEADER):
    """El texto de ``names`` extraído de ``path``, en su orden de la fuente.

    Se toman las sentencias de nivel superior (clases, funciones y
    asignaciones) sin modificar su texto; ``header`` aporta sólo lo que esas
    definiciones importan.
    """
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if _defined_names(node) & set(names)]
    found = set().union(*(_defined_names(node) for node in nodes))
    missing = set(names) - found
    assert not missing, f'faltan {missing}'
    return header + '\n'.join(ast.unparse(node) for node in nodes)


def load_misc_definitions(root, names, header):
    """Un módulo con ``names`` de ``odoo/tools/misc.py`` de la referencia."""
    module = types.ModuleType('reference_misc_definitions')
    path = pathlib.Path(root) / 'odoo' / 'tools' / 'misc.py'
    exec(compile(misc_definitions(path, names, header), str(path), 'exec'),
         module.__dict__)
    return module


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _package(name):
    module = types.ModuleType(name)
    module.__path__ = []
    sys.modules[name] = module
    return module


@contextlib.contextmanager
def _isolated(prefixes):
    saved = {name: module for name, module in sys.modules.items()
             if name.split('.')[0] in prefixes}
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in [n for n in sys.modules if n.split('.')[0] in prefixes]:
            del sys.modules[name]
        sys.modules.update(saved)


def load_reference_domains(root):
    """El módulo ``odoo.orm.domains`` de la referencia en ``root``."""
    root = pathlib.Path(root)
    with _isolated({'odoo', 'psycopg2'}):
        driver = types.ModuleType('psycopg2')
        driver.NotSupportedError = type('NotSupportedError', (Exception,), {})
        sys.modules['psycopg2'] = driver
        root_package = _package('odoo')
        root_package.exceptions = _load(
            'odoo.exceptions', root / 'odoo' / 'exceptions.py')
        tools = _package('odoo.tools')
        misc = types.ModuleType('odoo.tools.misc')
        exec(compile(misc_definitions(root / 'odoo' / 'tools' / 'misc.py'),
                     'misc.py', 'exec'), misc.__dict__)
        sys.modules['odoo.tools.misc'] = misc
        tools.misc = misc
        _load('odoo.tools.float_utils',
              root / 'odoo' / 'tools' / 'float_utils.py')
        sql = _load('odoo.tools.sql', root / 'odoo' / 'tools' / 'sql.py')
        query = _load('odoo.tools.query', root / 'odoo' / 'tools' / 'query.py')
        func = _load('odoo.tools.func', root / 'odoo' / 'tools' / 'func.py')
        tools.date_utils = _load('odoo.tools.date_utils',
                                 root / 'odoo' / 'tools' / 'date_utils.py')
        tools.SQL, tools.Query = sql.SQL, query.Query
        tools.classproperty = func.classproperty
        for name in ('OrderedSet', 'partition', 'str2bool'):
            setattr(tools, name, getattr(misc, name))
        _package('odoo.orm')
        _load('odoo.orm.identifiers', root / 'odoo' / 'orm' / 'identifiers.py')
        _load('odoo.orm.utils', root / 'odoo' / 'orm' / 'utils.py')
        return _load('odoo.orm.domains', root / 'odoo' / 'orm' / 'domains.py')


@contextlib.contextmanager
def runtime():
    """``odoo.orm.models`` sustituto durante una llamada a la referencia.

    ``DomainCondition.checked`` importa ``BaseModel`` en cada llamada sólo
    para un ``isinstance``. El sustituto es una clase vacía: ningún valor de
    las pruebas es un modelo, así que esa rama no se ejecuta en ningún lado.
    """
    name = 'odoo.orm.models'
    saved = sys.modules.get(name)
    models = types.ModuleType(name)
    models.BaseModel = type('BaseModel', (), {})
    sys.modules[name] = models
    try:
        yield
    finally:
        if saved is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = saved
