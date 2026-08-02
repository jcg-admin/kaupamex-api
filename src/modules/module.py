"""Descubrimiento de addons y lectura de manifiestos — fiel a ``odoo/modules/module.py``.

Conserva la superficie pública de la referencia (``MANIFEST_NAMES``,
``_DEFAULT_MANIFEST``, ``Manifest``, ``get_module_path``, ``load_manifest``,
``get_manifest``, ``get_modules``, ``get_modules_with_version``,
``adapt_version``, ``check_version``, ``MissingDependency``,
``check_python_external_dependency``) para que un addon portado se lea como su
fuente.

**Divergencias deliberadas** frente a la referencia:

- ``initialize_sys_path`` / ``load_openerp_module`` / ``load_script`` / los
  ``UpgradeHook``: NO se portan. Son el importador dinámico de Odoo
  (``addons_path`` + ``sys.meta_path``); aquí los addons son paquetes Python
  normales bajo ``src/addons/`` y los importa Python.
- ``get_module_icon`` / ``get_resource_from_path``: NO se portan (sirven al
  servidor de assets de Odoo).
- La raíz de addons es **una** (``src/addons``), no una lista ``addons_path``:
  este árbol no monta addons de terceros.
- ``version`` se normaliza contra ``release.series`` de Kaupamex, no contra la
  serie de Odoo — ``adapt_version`` es fiel en forma, no en el valor.
"""
from __future__ import annotations

import ast
import importlib.util
import typing
from collections.abc import Mapping
from pathlib import Path

import release

MANIFEST_NAMES = ['__manifest__.py']

# Raíz única de addons (≙ ``addons_path`` de la referencia, aquí singular).
ADDONS_PATH = Path(__file__).resolve().parent.parent / 'addons'

# Defaults del manifest. Calca ``_DEFAULT_MANIFEST`` de la referencia, podado a
# las claves que este árbol puede honrar: se omiten las de temas de website
# (``configurator_snippets``, ``images_preview_theme``, …), las de assets QWeb y
# los hooks del instalador dinámico, porque no hay quién las consuma. Declarar
# claves que nadie lee es peor que no declararlas: aparentan contrato.
_DEFAULT_MANIFEST = {
    # Obligatorias, sin default: author, license, name.
    'application': False,
    'auto_install': False,
    'category': 'Uncategorized',
    'countries': [],
    'depends': [],
    'description': '',
    'external_dependencies': {},
    'installable': True,
    'sequence': 100,
    'summary': '',
    'version': '1.0',
}

_MANDATORY = ('name', 'license')


class MissingDependency(Exception):
    """Dependencia externa declarada que no está instalada.

    Fiel a la de la referencia. La levanta ``check_python_external_dependency``.
    """


class Manifest(Mapping):
    """Manifest de un addon, con defaults aplicados — ≙ ``Manifest`` de la referencia.

    Es un ``Mapping`` inmutable: ``manifest['depends']`` y ``manifest.depends``
    son equivalentes, como en la referencia.
    """

    __slots__ = ('_data', 'name', 'path')

    def __init__(self, name: str, path: Path, data: dict):
        self.name = name
        self.path = path
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __getattr__(self, key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(key) from None

    def __repr__(self):
        return f'Manifest({self.name!r})'


def get_module_path(module: str, display_warning: bool = True) -> str | None:
    """Ruta del addon, o ``None`` si no existe. ≙ referencia."""
    path = ADDONS_PATH / module
    if (path / '__init__.py').is_file():
        return str(path)
    return None


def _load_manifest(module: str, manifest_content: dict) -> dict:
    """Aplica defaults y deriva campos. ≙ ``_load_manifest`` de la referencia."""
    manifest = dict(_DEFAULT_MANIFEST)
    manifest.update(manifest_content)
    # ``author`` es obligatorio en la referencia; aquí se deriva del release
    # cuando el addon no lo declara, porque todos son first-party.
    manifest.setdefault('author', release.author)
    manifest['version'] = adapt_version(str(manifest['version']))
    if isinstance(manifest['depends'], (list, tuple)):
        manifest['depends'] = list(manifest['depends'])
    return manifest


def load_manifest(module: str, mod_path: str | None = None) -> dict:
    """Lee el ``__manifest__.py`` del addon y devuelve el dict con defaults.

    Devuelve ``{}`` si el addon no existe o no tiene manifest — igual que la
    referencia, que trata la ausencia como "no es un módulo", no como error.

    El manifest se evalúa con ``ast.literal_eval``, **no** con ``eval``: es un
    literal de datos y no debe poder ejecutar código.
    """
    mod_path = mod_path or get_module_path(module, display_warning=False)
    if not mod_path:
        return {}

    for name in MANIFEST_NAMES:
        manifest_path = Path(mod_path) / name
        if manifest_path.is_file():
            break
    else:
        return {}

    try:
        content = ast.literal_eval(manifest_path.read_text(encoding='utf-8'))
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f'{module}: manifest ilegible ({manifest_path}): {exc}') from exc

    if not isinstance(content, dict):
        raise ValueError(f'{module}: el manifest debe ser un dict, no {type(content).__name__}')

    missing = [k for k in _MANDATORY if k not in content]
    if missing:
        raise ValueError(f'{module}: faltan claves obligatorias en el manifest: {missing}')

    return _load_manifest(module, content)


def get_manifest(module: str, mod_path: str | None = None) -> Mapping[str, typing.Any]:
    """``Manifest`` del addon, o un mapping vacío si no lo tiene. ≙ referencia."""
    data = load_manifest(module, mod_path)
    if not data:
        return {}
    return Manifest(module, Path(mod_path or get_module_path(module)), data)


def get_modules() -> list[str]:
    """Todos los addons del árbol (tengan manifest o no). ≙ referencia.

    Criterio: directorio con ``__init__.py`` bajo la raíz de addons. Es más
    ancho que "tiene manifest" a propósito — así ``get_modules()`` mide el
    universo real y el hueco de manifiestos es visible en vez de invisible.
    """
    if not ADDONS_PATH.is_dir():
        return []
    return sorted(
        p.name for p in ADDONS_PATH.iterdir()
        if p.is_dir() and (p / '__init__.py').is_file()
    )


def get_modules_with_version() -> dict[str, str]:
    """``{addon: version}`` de los addons **con** manifest. ≙ referencia."""
    out = {}
    for module in get_modules():
        manifest = load_manifest(module)
        if manifest:
            out[module] = manifest['version']
    return out


def adapt_version(version: str) -> str:
    """Prefija la serie de la plataforma si el addon declara sólo la suya.

    Fiel en forma a la referencia (que antepone ``release.series``), con **su**
    serie: aquí es la de Kaupamex, no la de Odoo.
    """
    serie = release.series
    if version == serie or version.startswith(f'{serie}.'):
        return version
    return f'{serie}.{version}'


def check_version(version: str, should_raise: bool = True) -> bool:
    """¿La versión del addon pertenece a la serie de la plataforma? ≙ referencia."""
    if version.startswith(f'{release.series}.'):
        return True
    if should_raise:
        raise ValueError(
            f'La versión {version!r} no pertenece a la serie {release.series!r}'
        )
    return False


def check_python_external_dependency(pydep: str) -> None:
    """Verifica que una dependencia externa declarada esté instalada. ≙ referencia.

    Levanta ``MissingDependency`` si falta. Se usa con
    ``manifest['external_dependencies']['python']`` — p. ej. ``authz_ldap``
    declara ``python-ldap``, que es un extra opcional porque compila contra
    libldap del sistema (igual que su ``__manifest__`` en la referencia, que lo
    declara con fallback apt).
    """
    # El nombre de distribución puede diferir del importable (``python-ldap`` →
    # ``ldap``); la referencia hace el mismo mapeo por casos conocidos.
    module_name = {'python-ldap': 'ldap', 'python-magic': 'magic'}.get(pydep, pydep)
    module_name = module_name.replace('-', '_')
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        raise MissingDependency(
            f'Falta la dependencia externa {pydep!r} (import {module_name!r})'
        )
