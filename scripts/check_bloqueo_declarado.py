#!/usr/bin/env python3
"""Gate: un símbolo que no se portó declara su bloqueador en forma legible.

``porte-completo-no-parcial.md`` ya exige declarar **cuántos, cuáles y por
qué** al no portar un símbolo. Lo que no fijaba es **cómo se escribe**, y sin
forma fija la declaración es prosa: sirve para que un humano la lea, no para
que nada la recorra.

Y recorrerla es el punto. La frase *"no lo porté porque falta que algo lo
llame"* es una **arista dirigida** —``símbolo_bloqueado → símbolo_que_falta``—
y el orden en que hay que portar lo que queda sale de ordenar ese grafo, no de
buscar vecinos parecidos. Mientras las aristas vivan en prosa, no hay grafo.

Estado al escribir el gate, medido sobre ``src/`` y ``addons/``:

===========================================================  ====
marcas ``BLOQUEAD*`` en total                                  99
con la forma contable ``Porte BLOQUEADO — N de M símbolos``     2
que nombran algo en ``code-span``                              22
que fijan la DIRECCIÓN (``por`` / ``depende de`` / ``requiere``) 6
que remiten en vago (``ver el docstring``, ``ver abajo``)        7
===========================================================  ====

Las seis de la cuarta fila son las únicas aristas completas. En el resto ni
siquiera se puede saber qué extremo se está leyendo: ``_get_report_values está
BLOQUEADO`` nombra al **bloqueado**, y ``BLOQUEADO por la misma causa que
journal`` nombra al **bloqueador**. Mismo patrón, direcciones opuestas.

Las dos formas que este gate acepta — las dos ya existen en el árbol, no se
inventan aquí:

1. **Cabecera contable**, en el docstring del archivo o de la clase::

       Porte BLOQUEADO — 0 de 3 símbolos

2. **Arista por símbolo**, en su docstring o en el comentario contiguo::

       BLOQUEADO por ``stock.move._compute_picking_type_id`` — la FK plana
       nace en None y el tipo no se propaga. Sucesor: #527.

   El ``code-span`` es el **destino** de la arista: lo que falta. La
   preposición ``por`` es lo que fija la dirección, y es obligatoria por eso.

**``porque`` no cuenta, y es una decisión, no un descuido.** Hay líneas del
árbol que dicen ``BLOQUEADOS porque ``addons/analytic/migrations/`` no estaba
en el alcance``. Fijan la dirección igual de bien para un lector, pero abren
una oración subordinada: lo que sigue al ``code-span`` puede negarlo, y un
recorrido de grafo no lee subordinadas. Van al baseline y se reescriben cuando
alguien toque el archivo.

Control positivo del gate — dos líneas **reales del repo**, no fabricadas:
``account_analytic_line.py:85`` (``BLOQUEADO por … ``journal``.``) pasa
mientras sus cinco vecinas del mismo archivo fallan, y
``product_expiry/models/stock_picking.py:7`` (``Porte BLOQUEADO — 0 de 3
símbolos``) deja el archivo entero en cero.

Métrica: líneas que contienen ``BLOQUEAD`` en ``.py``, clasificadas por
forma sintáctica.
Ciega a: (1) el símbolo que no se portó y **no dejó marca ninguna** — el
no-porte silencioso, que por construcción no aparece aquí; ésa la mide
``check_porte_completo.py``, no este gate. (2) que el ``code-span`` nombre un
símbolo que exista de verdad: el gate lee la forma, no resuelve el destino.
Resolverlo es la tubería de orden (tarea #530), que necesita este gate antes.
(3) la marca **repetida palabra por palabra en el mismo archivo**: la clave del
baseline es ``ruta::texto``, no la línea, para que no caduque a la primera
edición — y esa elección funde las repeticiones. Medido al congelar: 103 marcas
informes colapsan en 99 claves. Corregir una de un par deja la otra sin
bloquear hasta que su texto cambie.

Uso:
    check_bloqueo_declarado.py                     # todo el árbol
    check_bloqueo_declarado.py <archivos>          # sólo ésos
    check_bloqueo_declarado.py --write-baseline    # congela la deuda heredada
"""
import argparse
import os
import re
import sys

ROOTS = ('src', 'addons', 'tests')
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'bloqueo_declarado_baseline.txt')

MARKER = re.compile(r'BLOQUEAD[OA]S?\b')

# Forma 1 — la cabecera contable. El guion largo o el doble guion, porque las
# dos ortografías conviven en el árbol.
COUNTING_HEADER = re.compile(
    r'Porte\s+BLOQUEADO\s*(?:—|--|-)\s*\d+\s+de\s+\d+\s+s[ií]mbolos?')

# Forma 2 — la arista. La preposición fija la dirección; el code-span nombra
# el destino. `depende de` y `requiere` se aceptan como sinónimos porque ya
# están en uso y dicen exactamente lo mismo.
EDGE = re.compile(
    r'BLOQUEAD[OA]S?\b[^`]{0,40}?\b(?:por|depende\s+de|requiere)\b[^`]{0,20}``[^`]+``')


def source_files(paths):
    """Los ``.py`` a medir: los indicados, o el barrido de las raíces."""
    if paths:
        return [p for p in paths if p.endswith('.py') and os.path.exists(p)]
    found = []
    for root in ROOTS:
        for base, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
            found.extend(os.path.join(base, n) for n in names if n.endswith('.py'))
    return sorted(found)


#: La costura de una concatenación implícita de Python: la comilla que cierra
#: un trozo, la sangría, y la que abre el siguiente. En el texto **no existe**
#: —es sintaxis— así que al medir la forma se retira.
SEAM = re.compile(r"""['"]\s+['"]""")


def join_wrapped(line, following):
    """Une la línea de la marca con su continuación, sin la costura.

    Sin retirar la costura, un ``help_text`` partido mete unos veinte
    caracteres de sangría y comillas entre la preposición y el code-span, y la
    arista deja de casar por la ventana de :data:`EDGE` — que es estrecha a
    propósito, para que no cuele prosa ajena entre las dos mitades.

    Medido al cablearlo: dos marcas de ``addons/hr/models/hr_version.py``
    estaban en la forma fija y el gate las reportaba igual, sólo por dónde caía
    el corte de línea. La forma es del texto, no del ancho de la columna.
    """
    return SEAM.sub(' ', line.rstrip() + ' ' + following.strip())


def offenders_in(path):
    """Marcas de bloqueo que no adoptan ninguna de las dos formas.

    Devuelve ``(numero_de_linea, texto)`` por cada marca informe. Una marca
    que aparece dentro de una cabecera contable ya declarada en el mismo
    archivo NO se exime: la cabecera cuenta, la arista dirige, y hacen falta
    las dos para que el grafo tenga nodos y aristas.
    """
    try:
        lines = open(path, encoding='utf-8').read().split('\n')
    except (UnicodeDecodeError, OSError):
        return []
    bad = []
    for n, line in enumerate(lines, 1):
        if not MARKER.search(line):
            continue
        if COUNTING_HEADER.search(line) or EDGE.search(line):
            continue
        # La arista puede envolverse a la línea siguiente; el destino sigue
        # siendo suyo. Se mide el par, no la línea suelta.
        pair = join_wrapped(line, lines[n] if n < len(lines) else '')
        if EDGE.search(pair):
            continue
        bad.append((n, line.strip()))
    return bad


def load_baseline():
    if not os.path.exists(BASELINE):
        return set()
    with open(BASELINE, encoding='utf-8') as handle:
        return {row.strip() for row in handle if row.strip()
                and not row.startswith('#')}


def key_of(path, line_number, text):
    """Identidad estable de una marca heredada: archivo + texto, no la línea.

    El número de línea se mueve con cualquier edición del archivo; el texto
    de la marca no. Anclar al número haría que el baseline caducara solo.
    """
    return f'{path}::{text}'


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--write-baseline', action='store_true')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    files = source_files(args.paths)
    marks = []
    for path in files:
        for line_number, text in offenders_in(path):
            marks.append((key_of(path, line_number, text), path, line_number, text))

    if args.write_baseline:
        with open(BASELINE, 'w', encoding='utf-8') as handle:
            handle.write(
                '# Deuda heredada de marcas de bloqueo sin forma fija.\n'
                '# Una marca listada NO bloquea; una NUEVA si. Se paga al tocar\n'
                '# el archivo — mismo criterio prospectivo que el baseline de\n'
                '# idioma. Al reescribir una marca, borrar su linea de aqui.\n')
            for key, _, _, _ in sorted(marks):
                handle.write(key + '\n')
        print(f'baseline escrito: {len(marks)} marcas congeladas '
              f'(alcance medido: {len(files)} archivos)')
        return 0

    baseline = load_baseline()
    fresh = [m for m in marks if m[0] not in baseline]

    if args.quiet:
        print(len(fresh))
        return 1 if fresh else 0

    for _, path, line_number, text in fresh:
        print(f'{path}:{line_number}: marca de bloqueo sin forma fija')
        print(f'    {text[:110]}')
    if fresh:
        print()
        print('  La forma es una de estas dos:')
        print('    Porte BLOQUEADO — N de M símbolos           (cabecera contable)')
        print('    BLOQUEADO por ``destino`` — razón.          (arista dirigida)')
        print('  El code-span nombra lo que FALTA, no lo que quedó sin portar.')
    verdict = 'OK' if not fresh else 'FALLA'
    print(f'{verdict}: {len(fresh)} marca(s) nueva(s) sin forma fija '
          f'(alcance medido: {len(files)} archivos, {len(marks)} marcas informes, '
          f'{len(baseline)} congeladas en baseline)')
    return 1 if fresh else 0


if __name__ == '__main__':
    sys.exit(main())
