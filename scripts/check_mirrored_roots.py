#!/usr/bin/env python3
"""Gate: todo archivo tiene contraparte en su raíz espejada.

Cierra la tarea **#334** (``H-API-569``, ``H-API-578``). Nace de que
``check_porte_completo.py`` compara símbolos **dentro de un archivo dado** —
si el archivo no existe del otro lado, no hay con qué compararlo, así que un
archivo entero fuera de sitio queda invisible a ese gate. Así se inventaron
``src/orm/model_naming.py`` y ``src/orm/model_extension.py`` (ninguno existe
en la referencia) mientras sus dos hogares correctos — ``registry.py`` y
``model_classes.py`` — ya estaban en el árbol. Lo detectó una persona
listando el directorio de la referencia, no un gate.

Las raíces espejadas
=====================

Cuatro pares, ``nuestra raíz`` ↔ ``raíz de la referencia`` (``FIXED_MIRRORED_ROOTS``
más una familia dinámica, una por addon que ya tenemos portado)::

    src/orm            ↔  odoo/orm
    src/tools          ↔  odoo/tools
    src/addons/base    ↔  odoo/addons/base
    addons/<x>         ↔  addons/<x>          (una por cada <x> que TENEMOS
                                                 y que la referencia también
                                                 declara)

Un addon **enteramente propio** del L0 (``authz``, ``helpdesk``,
``observability``, …) no tiene par en la referencia — no es una raíz
espejada, y este gate no lo mide: no hay "sitio correcto" que comparar contra
la nada. Eso lo audita el censo de addons, no éste.

Las dos direcciones — nunca se suman
=====================================

(a) **Archivo de la referencia sin contraparte nuestra** — hueco de porte:
    algo que la referencia declara y que aún no aterrizó en nuestro árbol.

(b) **Archivo nuestro sin contraparte en la referencia** — posible invención
    de sitio: el defecto que ``H-API-569``/``H-API-578`` documentan. Tiene
    positivos **legítimos** — mecanismos propios de la plataforma que
    la referencia no necesita (``src/orm/fields_nonstored.py`` — campo
    ``store=False``; ``src/orm/inherits.py`` — delegación ``_inherits``;
    ``src/orm/method_chain.py`` — encadenado vía ``api.depends``;
    ``src/orm/routers.py`` — ruteo multi-DB por *company*). Se declaran en
    ``mirrored_roots_baseline.txt`` con su motivo; uno declarado no bloquea,
    uno nuevo sí.

Cada dirección se reporta **por separado**, con su propio denominador — nunca
sumadas: un hueco de porte y una posible invención son defectos de forma
opuesta y mezclarlos en un solo número borra cuál es cuál.

Qué mide, y qué NO
===================

*Métrica:* ruta relativa de cada ``.py`` dentro de la raíz espejada (excluidos
``__pycache__`` y ``migrations``, que son mecanismo de nuestro framework y
nunca tienen contraparte), comparada por igualdad exacta de ruta entre los dos
lados.

*Ciega a:*

- **Un archivo renombrado o movido a otro subdirectorio dentro de la misma
  raíz.** Aparece como una entrada en cada dirección (nuestra "sin
  contraparte" + la de la referencia "sin contraparte") en vez de una sola
  "relocación" — el instrumento no intenta emparejar por contenido, sólo por
  ruta exacta. Es la forma segura: nunca oculta el par sólo porque el nombre
  se parece.
- **El contenido del archivo.** Un archivo homónimo en el mismo sitio pero con
  símbolos distintos pasa este gate — eso es ``check_porte_completo.py`` y
  ``check_symbol_home.py``, que operan un nivel más abajo.
- **Un addon entero sin empezar a portar.** Sólo entran a la comparación los
  addons que YA existen de nuestro lado; el resto no es un "hueco de sitio",
  es "addon no tocado" — otro instrumento, otra pregunta.

Uso
====

    python3 scripts/check_mirrored_roots.py                 # las 4 raíces
    python3 scripts/check_mirrored_roots.py --quiet         # sólo el conteo
    python3 scripts/check_mirrored_roots.py --strict        # exit 1 si hay incumplidores
    python3 scripts/check_mirrored_roots.py --todos         # lista también lo declarado
    python3 scripts/check_mirrored_roots.py src/orm         # una raíz concreta
    python3 scripts/check_mirrored_roots.py src/orm addons/account

Una ruta pedida que no es una raíz espejada conocida se avisa y se omite —
**nunca** se interpreta como "barre todo". Sin el árbol de la referencia el
gate no falla: informa y sale 0 (mide el entorno, no el código, si no está).
"""
import argparse
import os
import pathlib
import sys

#: Raíz del árbol que gobierna. Mismo nombre de variable de entorno que
#: ``check_porte_completo.py`` y ``check_symbol_home.py`` — es el contrato ya
#: establecido con quien clona el árbol de referencia aparte.
REFERENCE_ROOT = pathlib.Path(
    os.environ.get(
        'ODOO19C',
        '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0',
    )
)

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Los tres pares fijos. La cuarta raíz (``addons/<x>``) es una familia — se
#: expande en tiempo de ejecución con ``addon_roots()``, porque su lista
#: depende de qué addons tengamos hoy.
FIXED_MIRRORED_ROOTS = (
    ('src/orm', REPO / 'src' / 'orm', REFERENCE_ROOT / 'odoo' / 'orm'),
    ('src/tools', REPO / 'src' / 'tools', REFERENCE_ROOT / 'odoo' / 'tools'),
    ('src/addons/base', REPO / 'src' / 'addons' / 'base',
     REFERENCE_ROOT / 'odoo' / 'addons' / 'base'),
)

#: Directorios cuyo contenido nunca tiene contraparte — mecanismo del
#: framework (Django), no decisión de porte. Mismo criterio que
#: ``check_symbol_home.py::clases_propias``.
EXCLUDED_DIR_NAMES = frozenset({'__pycache__', 'migrations'})

BASELINE_PATH = pathlib.Path(__file__).resolve().parent / 'mirrored_roots_baseline.txt'


def addon_roots():
    """Un par ``(label, our_path, reference_path)`` por cada addon que YA TENEMOS
    y que la referencia también declara.

    Un addon nuestro sin par en la referencia (``authz``, ``helpdesk``,
    ``observability``, ``sale_subscription``, …) no entra: no es una raíz
    espejada, es un addon propio del L0 completo. Incluirlo inundaría el
    reporte con "sin contraparte" para cada uno de sus archivos — ruido, no
    la señal que este gate busca.
    """
    addons_dir = REPO / 'addons'
    if not addons_dir.is_dir():
        return
    for entry in sorted(addons_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith('.'):
            continue
        reference_addon = REFERENCE_ROOT / 'addons' / entry.name
        if reference_addon.is_dir():
            yield (f'addons/{entry.name}', entry, reference_addon)


def all_mirrored_roots():
    """Las tres fijas más la familia de addons — el barrido por defecto."""
    return list(FIXED_MIRRORED_ROOTS) + list(addon_roots())


def _resolved_candidates(requested):
    """Las formas en que ``requested`` podría resolver a una raíz conocida.

    Admite tanto una ruta relativa al cwd como relativa a la raíz del repo —
    el uso típico es correr el gate desde ``kaupamex-api/``, pero no hay por
    qué exigirlo.
    """
    path = pathlib.Path(requested)
    if path.is_absolute():
        return {str(path.resolve())}
    return {
        str((pathlib.Path.cwd() / path).resolve()),
        str((REPO / path).resolve()),
    }


def select_roots(requested_paths):
    """Sin argumentos: las cuatro raíces. Con argumentos: sólo las pedidas.

    Una ruta que no matchea ninguna raíz conocida se avisa por stderr y se
    omite — nunca degrada a "barrer todo", que es justo el anti-patrón que
    esta función existe para no cometer.
    """
    all_roots = all_mirrored_roots()
    if not requested_paths:
        return all_roots
    by_path = {str(ours.resolve()): (label, ours, reference)
               for label, ours, reference in all_roots}
    selected = []
    for requested in requested_paths:
        candidates = _resolved_candidates(requested) & by_path.keys()
        if candidates:
            selected.append(by_path[next(iter(candidates))])
        else:
            print(f'check_mirrored_roots: {requested!r} no es una raíz '
                  f'espejada conocida — se omite.', file=sys.stderr)
    return selected


def list_py_files(root):
    """Rutas relativas (con ``/``) de los ``.py`` de ``root``.

    Excluye ``__pycache__`` y ``migrations`` en cualquier profundidad — son
    mecanismo, no porte. Si ``root`` no existe, el conjunto es vacío (no es
    un error: puede ser el lado nuestro de un addon aún sin empezar).
    """
    if not root.is_dir():
        return set()
    found = set()
    for path in root.rglob('*.py'):
        parts = path.relative_to(root).parts
        if any(p in EXCLUDED_DIR_NAMES for p in parts[:-1]):
            continue
        found.add('/'.join(parts))
    return found


def repo_relative_path(path):
    """La ruta, relativa a ``REPO`` y con ``/`` — la clave que usa el baseline."""
    return str(path.resolve().relative_to(REPO)).replace(os.sep, '/')


def compare_root(ours, reference):
    """Los conjuntos de ambos lados y las dos direcciones, para una raíz sola.

    Función pura — sin ``print`` ni baseline — para que un test la ejercite
    sin pasar por ``main()`` ni por el filesystem real del repo.
    """
    our_files = list_py_files(ours)
    reference_files = list_py_files(reference)
    porting_gaps = sorted(reference_files - our_files)         # dirección (a)
    without_counterpart = sorted(our_files - reference_files)  # dirección (b)
    return our_files, reference_files, porting_gaps, without_counterpart


def load_baseline():
    """Mapa ``path::motivo`` — sólo cubre la dirección (b) (posible invención).

    La dirección (a) —huecos de porte— nunca se declara aquí: es justo lo que
    este gate existe para seguir mostrando, no para silenciar.
    """
    baseline = {}
    if not BASELINE_PATH.is_file():
        return baseline
    for entry_line in BASELINE_PATH.read_text(encoding='utf-8').splitlines():
        entry_line = entry_line.strip()
        if not entry_line or entry_line.startswith('#') or '::' not in entry_line:
            continue
        key, reason = entry_line.split('::', 1)
        baseline[key.strip()] = reason.strip()
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('paths', nargs='*',
                        help='raíces nuestras a auditar (por defecto, las cuatro)')
    parser.add_argument('--quiet', action='store_true',
                        help='sólo las líneas de conteo')
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si hay huecos o invenciones nuevas')
    parser.add_argument('--todos', action='store_true',
                        help='listar también lo ya declarado en el baseline')
    args = parser.parse_args()

    if not REFERENCE_ROOT.is_dir():
        print(f'check_mirrored_roots: árbol de referencia ausente '
              f'({REFERENCE_ROOT}) — gate omitido, no es un fallo.')
        return 0

    roots = select_roots(args.paths)
    if not roots:
        print('check_mirrored_roots: ninguna raíz espejada para auditar.')
        return 0

    baseline = load_baseline()

    porting_gaps = []       # dirección (a): en la referencia, no en nosotros
    new_inventions = []     # dirección (b): en nosotros, no en la referencia
    declared_inventions = []
    total_reference_files = 0
    total_our_files = 0

    for label, ours, reference in roots:
        our_files, reference_files, gaps, without_counterpart = compare_root(ours, reference)
        total_our_files += len(our_files)
        total_reference_files += len(reference_files)

        for rel in gaps:
            porting_gaps.append((label, rel))

        for rel in without_counterpart:
            key = repo_relative_path(ours / rel)
            if key in baseline:
                declared_inventions.append((label, rel, baseline[key]))
            else:
                new_inventions.append((label, rel))

    if not args.quiet:
        for label, rel in porting_gaps:
            print(f'HUECO DE PORTE    {label}/{rel}')
        for label, rel in new_inventions:
            print(f'SIN CONTRAPARTE   {label}/{rel}')
        if args.todos:
            for label, rel, reason in declared_inventions:
                print(f'declarado         {label}/{rel} — {reason}')

    # El denominador va junto al conteo: sin él, un instrumento ciego (que
    # nunca mira nada) y uno correcto publican el mismo cero
    # (`hallazgo-abierto-genera-sucesor.md` / `metrica-decide-la-conclusion.md`).
    print(f'check_mirrored_roots: {len(porting_gaps)} de la referencia sin '
          f'contraparte nuestra (alcance medido: {total_reference_files} '
          f'archivos de referencia en {len(roots)} raíces).')
    print(f'check_mirrored_roots: {len(new_inventions)} nuestros sin '
          f'contraparte en la referencia, {len(declared_inventions)} '
          f'declarados en baseline (alcance medido: '
          f'{total_our_files} archivos nuestros en {len(roots)} raíces).')

    if args.strict and (porting_gaps or new_inventions):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
