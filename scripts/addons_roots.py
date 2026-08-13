"""Las raíces de addons — leídas del producto, no copiadas aquí.

El layout lo declara ``src/modules/module.py`` (``ADDONS_PATHS``, ≙
``addons_base_dir`` + ``addons_community_dir`` de la referencia). Los gates lo
**consultan**; no lo redeclaran.

La dirección de la dependencia es deliberada: si el producto añade o mueve una
raíz, los gates la siguen sin que nadie los edite. Al revés —cada gate con su
copia de la ruta— es exactamente la segunda fuente de verdad que
``calibration-verified-numbers.md`` prohíbe, y su modo de fallo es silencioso:
un gate que apunta a una raíz vacía publica ``0 incumplidores`` y parece sano.
Ese cero ya se pagó una vez (:ref:`h-api-335`).

No importa Django: ``modules.module`` sólo depende de la stdlib y de
``release``, así que un gate sigue corriendo con ``python3 scripts/<x>.py``.
"""
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from modules.module import ADDONS_BASE_DIR, ADDONS_COMMUNITY_DIR, ADDONS_PATHS  # noqa: E402

# Relativas al repo — la forma en que los gates imprimen sus rutas.
ADDONS_ROOTS_REL = tuple(str(p.relative_to(REPO_ROOT)) for p in ADDONS_PATHS)


def addon_dirs():
    """Todo directorio de addon, de cualquier raíz. Ordenado y sin duplicados.

    Devuelve rutas absolutas. Un addon presente en las dos raíces aparece una
    vez, con la precedencia de ``ADDONS_PATHS`` (base primero) — la misma que
    ``get_module_path`` aplica al resolver.
    """
    vistos = {}
    for root in ADDONS_PATHS:
        if not root.is_dir():
            continue
        for p in sorted(root.iterdir()):
            if p.is_dir() and p.name not in vistos and not p.name.startswith('__'):
                vistos[p.name] = p
    return [vistos[n] for n in sorted(vistos)]


def addon_root_of(nombre):
    """La raíz que contiene al addon, o ``None`` si no está en ninguna."""
    for root in ADDONS_PATHS:
        if (root / nombre / '__init__.py').is_file():
            return root
    return None


def addon_path(nombre):
    """Directorio del addon, resuelto por precedencia. ``None`` si no existe."""
    root = addon_root_of(nombre)
    return root / nombre if root else None


def addon_names():
    """Nombres de addon, ordenados y únicos."""
    return [p.name for p in addon_dirs()]


def py_files():
    """Todo ``.py`` bajo cualquier raíz de addons, ordenado por raíz.

    Sustituye al ``rglob`` sobre una raíz única: con dos raíces, recorrer sólo
    una devuelve un universo parcial y su silencio se lee como ausencia.
    """
    for root in ADDONS_PATHS:
        if root.is_dir():
            yield from sorted(root.rglob('*.py'))


__all__ = [
    'ADDONS_BASE_DIR', 'ADDONS_COMMUNITY_DIR', 'ADDONS_PATHS',
    'ADDONS_ROOTS_REL', 'REPO_ROOT', 'addon_dirs', 'addon_root_of',
]
