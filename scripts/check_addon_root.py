#!/usr/bin/env python3
"""Un addon vive en UNA sola raíz — el gate del reparto de ``ADDONS_PATHS``.

El namespace ``addons`` abarca las dos raíces que ``modules.module`` declara
(``ADDONS_BASE_DIR`` y ``ADDONS_COMMUNITY_DIR``): ``initialize_sys_path`` las
apenda ambas a ``addons.__path__``, en ese orden. Esa es la propiedad que hace
que mover un addon de una raíz a otra **no** obligue a reescribir ningún
``import`` — y es también la que vuelve invisible el defecto que este gate
mide.

El defecto
----------

Si un mismo nombre de addon existe bajo las dos raíces, Python resuelve
``addons.<nombre>`` contra la **primera** del ``__path__`` y la otra copia
queda muerta: no falla el arranque, no falla la suite, no falla ningún import.
Los archivos de la copia perdedora simplemente no se ejecutan nunca.

La forma canónica en que aparece no es un error de tecleo, sino un merge: una
rama reubica un addon y otra, en paralelo, añade archivos **nuevos** en la ruta
vieja. La detección de renombres de git reubica lo que puede aparear, pero un
directorio recién creado no tiene contraparte que aparear, así que aterriza
donde lo dejó la otra rama. El resultado es un addon partido entre las dos
raíces, y nada del stack lo señala.

Qué mide, y qué NO
------------------

*Métrica:* nombres de directorio de addon que aparecen bajo más de una raíz de
``ADDONS_PATHS``.
*Ciega a:* un archivo suelto colocado en la raíz equivocada de un addon que
**sólo** existe ahí (no hay partición que ver); y a un addon partido por
contenido dentro de una misma raíz.

Uso
---

    python3 scripts/check_addon_root.py            # reporte
    python3 scripts/check_addon_root.py --quiet    # sólo el conteo
    python3 scripts/check_addon_root.py --strict   # exit 1 si hay partidos
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'src'))

from modules.module import ADDONS_PATHS


def addon_dirs(root: Path) -> set[str]:
    """Nombres de subdirectorio que parecen un addon (paquete Python)."""
    if not root.is_dir():
        return set()
    return {
        entry.name
        for entry in root.iterdir()
        if entry.is_dir()
        and not entry.name.startswith(('.', '__'))
        and (entry / '__init__.py').exists()
    }


def split_addons(roots=ADDONS_PATHS) -> tuple[dict[str, list[Path]], int]:
    """Devuelve los addons partidos y el total medido (el denominador)."""
    ubicaciones: dict[str, list[Path]] = defaultdict(list)
    for root in roots:
        for nombre in addon_dirs(Path(root)):
            ubicaciones[nombre].append(Path(root))
    partidos = {n: r for n, r in ubicaciones.items() if len(r) > 1}
    return partidos, len(ubicaciones)


def main() -> int:
    quiet = '--quiet' in sys.argv
    strict = '--strict' in sys.argv

    partidos, total = split_addons()

    if quiet:
        print(len(partidos))
        return 1 if (strict and partidos) else 0

    if not partidos:
        print(f'OK: ningún addon partido entre raíces '
              f'(alcance medido: {total} addons en {len(ADDONS_PATHS)} raíces)')
        return 0

    print(f'FALLA: {len(partidos)} addon(s) existen bajo más de una raíz '
          f'(alcance medido: {total} addons en {len(ADDONS_PATHS)} raíces).')
    print('Python resuelve el import contra la PRIMERA raíz; la otra copia '
          'queda muerta sin avisar.\n')
    for nombre in sorted(partidos):
        print(f'  {nombre}')
        for root in partidos[nombre]:
            ruta = Path(root) / nombre
            archivos = sum(1 for _ in ruta.rglob('*.py'))
            print(f'      {ruta}  ({archivos} .py)')
    print('\nArreglo: consolidar el addon en la raíz que le corresponde '
          '(git mv), no duplicar.')
    return 1 if strict else 0


if __name__ == '__main__':
    raise SystemExit(main())
