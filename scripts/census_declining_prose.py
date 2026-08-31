#!/usr/bin/env python3
"""Censa la prosa que declina un porte, y separa la anclada de la que no.

Tarea **#250**, sucesora de :ref:`h-api-974`. Aquel hallazgo registro dos
bloques de prosa que declinaban portar un campo ``related=`` dando como razon
que un ``related`` es *«una copia que puede divergir»* — descripcion de
``store=True``, que **552 de los 597** que la referencia declara no llevan.

El defecto no eran esos dos bloques: es que **una razon escrita en prosa no
tiene con que medirse** y envejece sin que nada lo note. Este guion es el
instrumento del barrido.

El corte que publica
====================

Una razon **anclada** a la fuente —cita ``odoo19c:``, un ``:NNN``, «la
fuente», «la referencia», el signo ``≙`` o un hallazgo— se puede contrastar
contra el arbol de la referencia. Una **sin ancla** no: describe una decision
nuestra sin nada que la sostenga, que es exactamente el caso que H-API-974
refuto.

*Metrica:* lineas de ``src/`` y ``addons/`` que casan con un marcador de
declinacion, clasificadas por si su bloque —seis lineas a cada lado— contiene
un ancla.

*Ciega a:* la declinacion escrita sin ninguno de los marcadores; la que vive
en un ``.rst``; el ancla que este mas lejos que seis lineas —los encabezados
del tipo «Que NO se porta, con su medicion» caen ahi, y su medicion viene
debajo—; y el ancla presente que apunte a otra cosa. Es una **cota**, no un
conteo exacto de razones sin sostener.
"""
import argparse
import collections
import pathlib
import re
import sys

#: Las formas con que este arbol declina un porte, medidas sobre el corpus.
DECLINE_MARKERS = re.compile(
    r'no se porta|no se portan|se omite|se omiten|no aporta|puede divergir|'
    r'no aplica aqu|no tiene sentido aqu|se descarta|no se declara|'
    r'no hace falta|no lo necesitamos|se deja fuera', re.I)

#: Lo que hace contrastable una razon: una cita de la referencia o de un
#: hallazgo que ya la midio.
ANCHOR = re.compile(r'odoo1[89][ce]:|``:\d+|la fuente|la referencia|≙|:ref:`h-')

#: Cuantas lineas a cada lado cuentan como el bloque de la razon.
CONTEXT = 6

ROOTS = ('src', 'addons')


def scan(repo_root):
    """``(ancladas, sin_ancla)`` — dos listas de ``(ruta, linea, texto)``."""
    anchored, unanchored = [], []
    for root in ROOTS:
        for path in sorted((repo_root / root).rglob('*.py')):
            try:
                lines = path.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for index, line in enumerate(lines):
                if not DECLINE_MARKERS.search(line):
                    continue
                block = '\n'.join(
                    lines[max(0, index - CONTEXT):index + CONTEXT + 1])
                row = (str(path.relative_to(repo_root)), index + 1,
                       line.strip()[:110])
                (anchored if ANCHOR.search(block) else unanchored).append(row)
    return anchored, unanchored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sin-ancla', action='store_true',
                        help='lista sólo las razones sin ancla a la fuente')
    parser.add_argument('--prefijo', default='',
                        help='acota a las rutas que empiecen así')
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).parent.parent
    anchored, unanchored = scan(repo_root)
    total = len(anchored) + len(unanchored)
    if not total:
        # Un 0 aqui no distinguiria «no hay declinaciones» de «el recorrido no
        # vio ningun archivo», que es el verde falso de H-API-335.
        sys.exit('ERROR — 0 lineas medidas sobre ninguna raiz. NO se emite conteo.')

    listed = unanchored if args.sin_ancla else anchored + unanchored
    listed = [r for r in listed if r[0].startswith(args.prefijo)]
    for path, number, text in listed:
        print(f'{path}:{number}  {text}')

    by_file = collections.Counter(row[0] for row in anchored + unanchored)
    print(f'\n(alcance medido: {total} linea(s) con marcador en '
          f'{len(by_file)} archivo(s) bajo {"/, ".join(ROOTS)}/; '
          f'{len(anchored)} con ancla a la fuente, {len(unanchored)} sin ella; '
          f'listadas aqui: {len(listed)})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
