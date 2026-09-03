#!/usr/bin/env python3
"""El orden en que conviene portar ``odoo/orm/`` — derivado, no elegido.

El defecto que este guion existe para cerrar
=============================================

El porte venia avanzando **por orden de lectura**: se abria un archivo de la
referencia, se portaba lo que declaraba, y al primer simbolo que necesitaba
otro sin portar el trabajo quedaba a medias. El orden de lectura no tiene
ninguna relacion con el orden de dependencia, asi que cada tramo pagaba el
mismo peaje: descubrir a mitad de camino que faltaba algo de abajo.

La pregunta correcta no es *«que archivo sigue»* sino **«que puedo portar
ahora sin chocar, y cuanto desbloquea»**. Eso es una propiedad del grafo de
dependencias, y se calcula.

Los tres algoritmos y por que estos
====================================

Cada uno vive en su propio modulo, con la decision que lo eligio — son tres
responsabilidades distintas y cambian por razones distintas (SRP). Aqui solo
su papel en esta pregunta:

1. **Tarjan** — los ciclos. Un ciclo se porta **entero o no se porta**: si
   ``A`` necesita ``B`` y ``B`` necesita ``A``, no hay primero. Fingir un
   orden dentro del ciclo es la unica forma de garantizar que el tramo quede
   a medias.
2. **Kahn por niveles**, sobre el grafo **condensado** (cada ciclo colapsado
   a un nodo). Su estado —cuantas dependencias le quedan a cada nodo— **es**
   la respuesta: el nivel N es lo que ya no bloquea nada de niveles previos.
3. **Brandes** — el desempate DENTRO de cada nivel. Los nodos de un mismo
   nivel son todos portables ya; lo que los distingue es cuanto abre cada uno.

   El criterio primario NO es la centralidad sino ``dep`` —cuantos simbolos
   dependen de este, transitivamente—, y esto es medido, no preferencia: en
   el nivel 1 la centralidad vale **cero para todos**, porque ese nivel son
   sumideros del grafo de dependencia y ningun camino pasa *a traves* de un
   sumidero. La centralidad discrimina en los niveles intermedios, que es
   donde hay caminos que atravesar.

Las dos capas de dependencia, que NO son la misma
==================================================

Una dependencia **dura** —herencia, decorador, cuerpo de clase— se resuelve
**al importar**: el simbolo tiene que existir antes, y si dos se necesitan
asi no hay primero. Una **blanda** —dentro de un metodo— se resuelve **al
llamar**: basta con que exista para entonces.

Mezclarlas fue la primera version de este guion, y publico un ciclo de **39
simbolos** —el 27 % de la raiz— como un bloque indivisible. Separadas, el
ciclo duro real es de **7**: ``BaseModel``, ``BaseString``, ``Char``,
``Field``, ``Id``, ``MetaModel`` y ``Registry``. La cifra de 39 era correcta
y la conclusion no se seguia — el instrumento medi­a «se nombran» y la
conclusion era «hay que portarlos a la vez».

El orden lo fija la capa dura. La blanda solo informa: ``llama=`` dice a
cuantos alcanza el simbolo por llamada, que es cuanto abre sin bloquear.

Que publica
===========

Por nivel: sus simbolos, ``dep`` (cuantos dependen de este por importacion),
``llama`` (por llamada), la centralidad, y si el nombre ya se declara aqui.
Un ciclo va marcado ``CICLO(n)`` con los simbolos que lo componen: se porta
entero o no se porta.

*Metrica:* nombres de simbolo referenciados en el cuerpo de cada clase o
funcion de nivel superior de ``odoo/orm/*.py``, por AST, contra el conjunto de
simbolos declarados en esa misma raiz.
*Ciega a:* (a) una dependencia que la fuente resuelva por cadena
(``env['res.partner']``) en vez de por nombre — no hay ``ast.Name`` que ver;
(b) una dependencia hacia **fuera** de ``odoo/orm`` (``odoo/tools``), que se
excluye a proposito: no bloquea dentro de esta raiz; (c) si el simbolo ya
esta portado **de verdad** — la columna ``aqui`` mide que el nombre se declara
en ``src/orm/`` en alguna forma (clase, funcion, asignacion o re-export), no
que haga lo mismo. Ese veredicto es la tarea #209;
(d) una anotacion de tipo diferida (``from __future__ import annotations``)
sigue contando como dura aunque no se evalue al importar, asi que el ciclo
duro es una **cota superior**: puede ser mas pequeno, nunca mayor.

Uso::

    uv run python scripts/orden_de_porte.py            # la secuencia entera
    uv run python scripts/orden_de_porte.py --pendiente # solo lo que falta aqui
"""
import argparse
import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import reference_roots  # noqa: E402

from graph_centrality import betweenness_centrality  # noqa: E402
from graph_components import cyclic_components  # noqa: E402
from graph_ordering import topological_levels  # noqa: E402

#: La raiz de la referencia que se ordena, y su espejo en este arbol.
REFERENCE_SUBPATH = ('odoo', 'orm')
OUR_SUBPATH = ('src', 'orm')

REPO = HERE.parent


def top_level_symbols(root):
    """``{nombre: (archivo, nodo)}`` de todo simbolo de nivel superior."""
    found = {}
    for path in sorted(root.glob('*.py')):
        for node in ast.parse(path.read_text(errors='ignore')).body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                found[node.name] = (path.name, node)
    return found


def declared_here(root):
    """``{nombre}`` de todo simbolo que esta raiz declare, en CUALQUIER forma.

    Responde una pregunta distinta de :func:`top_level_symbols`, y por eso es
    otra funcion: aquella enumera los **nodos que se ordenan** —clases y
    funciones, las unidades del grafo—; esta responde **«¿el nombre ya se
    declara aqui?»**, y para eso cuenta tambien la asignacion de nivel
    superior y el re-export.

    La asimetria es deliberada. Meter las asignaciones en la enumeracion de
    nodos cambiaria el grafo de la referencia —entrarian sus constantes de
    modulo— y con el los niveles, que es lo que el guion existe para calcular.
    Dejarlas fuera de este lado publica una ausencia falsa: medido, 12 de los
    27 que la columna ``aqui`` daba por ausentes existian, declarados como
    ``Boolean = make_dispatcher(...)`` o re-exportados. Es el sub-patron C de
    ``metrica-decide-la-conclusion.md`` — el instrumento mide la FORMA de la
    declaracion y se concluia sobre la PRESENCIA del simbolo.

    Una raiz que no existe devuelve el conjunto vacio: quien llama ya
    distingue ese caso, y levantar aqui obligaria a cada consumidor a
    envolverlo.
    """
    found = set()
    if not root.is_dir():
        return found
    for path in sorted(root.glob('*.py')):
        for node in ast.parse(path.read_text(errors='ignore')).body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                found.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.add(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    found.add(node.target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                # El re-export cuenta por su nombre LOCAL: es el que queda
                # disponible desde esta raiz.
                for alias in node.names:
                    found.add(alias.asname or alias.name.split('.')[0])
    return found


def names_used_by(node, *, inside_bodies):
    """Los nombres que este simbolo referencia, en UNA de sus dos capas.

    La distincion no es cosmetica: decide si dos simbolos hay que portarlos
    juntos o no.

    - ``inside_bodies=False`` — la capa **dura**: bases de la clase,
      decoradores, valores por defecto, y todo lo que el cuerpo de la clase
      evalua fuera de un metodo. Se resuelve **al importar**, asi que el
      simbolo tiene que existir antes; si dos se necesitan asi, no hay
      primero.
    - ``inside_bodies=True`` — la capa **blanda**: lo que ocurre dentro de un
      metodo o funcion. Se resuelve **al llamar**, asi que basta con que el
      nombre exista para entonces. Una dependencia blanda mutua NO es un
      bloqueo: se rompe portando primero la firma.

    Medirlas juntas fue la primera version de este guion, y publicaba un
    ciclo de 39 simbolos —el 27 % de la raiz— como un bloque indivisible.
    La cifra era correcta y la conclusion no se seguia: el instrumento medi­a
    «se nombran» y la conclusion era «hay que portarlos a la vez».
    """
    bodies = [n for n in ast.walk(node)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n is not node]
    inner = {id(n) for body in bodies for n in ast.walk(body)}

    used = set()
    for child in ast.walk(node):
        if child is node:
            continue
        if (id(child) in inner) != inside_bodies:
            continue
        if isinstance(child, ast.Name):
            used.add(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            used.add(child.value.id)
    return used


def build_graph(symbols, *, inside_bodies):
    """``{simbolo: {simbolos que necesita}}`` en una capa, acotado a esta raiz."""
    universe = set(symbols)
    edges = {}
    for name, (_, node) in symbols.items():
        needed = names_used_by(node, inside_bodies=inside_bodies) & universe
        needed.discard(name)          # recursion no es dependencia externa
        edges[name] = needed
    return edges


def reachable_dependents(edges, nodes):
    """Cuantos simbolos dependen de cada uno, directa o transitivamente.

    Es la medida de «cuanto desbloquea»: no cuantos vecinos tiene, sino a
    cuantos les abre el camino. Se calcula sobre el grafo invertido con un
    recorrido iterativo — el mismo motivo que Tarjan, la profundidad del
    grafo no cabe en la pila de Python.
    """
    inverse = {n: set() for n in nodes}
    for node, needed in edges.items():
        for dependency in needed:
            if dependency in inverse:
                inverse[dependency].add(node)
    counts = {}
    for start in nodes:
        seen, pending = set(), [start]
        while pending:
            current = pending.pop()
            for dependent in inverse.get(current, ()):
                if dependent not in seen:
                    seen.add(dependent)
                    pending.append(dependent)
        counts[start] = len(seen)
    return counts


def condense(nodes, edges, components):
    """Colapsa cada ciclo a un nodo unico. Devuelve ``(nodos, aristas, mapa)``."""
    of_group = {}
    for component in components:
        label = '+'.join(sorted(component))
        for member in component:
            of_group[member] = label
    for node in nodes:
        of_group.setdefault(node, node)

    grouped_nodes = sorted(set(of_group.values()))
    grouped_edges = {g: set() for g in grouped_nodes}
    for node, needed in edges.items():
        source = of_group[node]
        for dependency in needed:
            target = of_group.get(dependency)
            if target is not None and target != source:
                grouped_edges[source].add(target)
    return grouped_nodes, grouped_edges, of_group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pendiente', action='store_true',
                        help='omitir los niveles cuyos simbolos ya estan aqui')
    args = parser.parse_args()

    root = pathlib.Path(reference_roots.tree('odoo19c')).joinpath(*REFERENCE_SUBPATH)
    if not root.is_dir():
        # Rehusa con codigo propio en vez de emitir una secuencia vacia: un
        # cero aqui no distingue "no falta nada" de "no pude medir".
        raise SystemExit(
            f'ERROR — la referencia no esta en {root}. No se emite secuencia: '
            'una lista vacia sin fuente seria un verde falso.')

    symbols = top_level_symbols(root)
    # El orden lo fija la capa DURA; la blanda solo informa cuanto abre cada
    # tramo, porque una llamada se resuelve cuando ya existe todo.
    edges = build_graph(symbols, inside_bodies=False)
    soft = build_graph(symbols, inside_bodies=True)
    nodes = sorted(symbols)

    ours_root = REPO.joinpath(*OUR_SUBPATH)
    ours = declared_here(ours_root)

    components = cyclic_components(nodes, edges)
    grouped_nodes, grouped_edges, of_group = condense(nodes, edges, components)
    levels, trapped = topological_levels(grouped_nodes, grouped_edges)
    centrality = betweenness_centrality(nodes, edges)
    dependents = reachable_dependents(edges, nodes)
    soft_dependents = reachable_dependents(soft, nodes)

    print(f'=== {root.name}/ — {len(symbols)} simbolos de nivel superior '
          f'en {len(list(root.glob("*.py")))} archivos ===')
    hard_count = sum(len(v) for v in edges.values())
    soft_count = sum(len(v) for v in soft.values())
    print(f'aristas: {hard_count} duras (importacion) · {soft_count} blandas (llamada)')
    print(f'ciclos duros: {len(components)} · nodos tras condensar: {len(grouped_nodes)}')
    soft_cycles = cyclic_components(nodes, soft)
    print(f'ciclos si se mezclaran las dos capas: '
          f'{len(cyclic_components(nodes, {n: edges[n] | soft[n] for n in nodes}))} '
          f'(solo blandos: {len(soft_cycles)}) — no bloquean')
    print(f'aqui ya se declara el nombre: {len(set(nodes) & ours)} de {len(nodes)}')
    if trapped:
        # No deberia ocurrir tras condensar: si ocurre, el instrumento tiene
        # un hueco y se nombra en vez de callarlo.
        print(f'ATENCION — {len(trapped)} nodos sin nivel tras condensar: {trapped}')

    covered = 0
    for number, level in enumerate(levels, start=1):
        members = [(g, sorted(g.split('+'))) for g in level]
        pending = [(g, ms) for g, ms in members if not set(ms) <= ours]
        if args.pendiente and not pending:
            continue
        shown = pending if args.pendiente else members
        size = sum(len(ms) for _, ms in shown)
        opens = sum(max(dependents[m] for m in ms) for _, ms in shown)
        reach = sum(max(soft_dependents[m] for m in ms) for _, ms in shown)
        covered += size
        print(f'\n--- nivel {number}: {size} simbolos · '
              f'desbloquea {opens} por importacion, {reach} por llamada ---')
        shown.sort(key=lambda r: (-max(dependents[m] for m in r[1]),
                                  -max(centrality[m] for m in r[1]), r[0]))
        for group, ms in shown:
            here = 'aqui' if set(ms) <= ours else '    '
            mark = f'CICLO({len(ms)})' if len(ms) > 1 else ' ' * 9
            top = max(dependents[m] for m in ms)
            middle = max(centrality[m] for m in ms)
            llama = max(soft_dependents[m] for m in ms)
            print(f'  {here} {mark} dep={top:<4} llama={llama:<4} '
                  f'centro={middle:8.1f}  {", ".join(ms)}')

    print(f'\n### {covered} simbolos en {len(levels)} niveles ###')


if __name__ == '__main__':
    main()
