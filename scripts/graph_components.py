#!/usr/bin/env python3
"""Los ciclos de un grafo dirigido — que nodos se alcanzan mutuamente.

Responsabilidad unica: **decir que grupos de nodos forman un ciclo**. No
ordena nada ni pondera nada; esas son otras dos preguntas, y viven en
``graph_ordering.py`` y ``graph_centrality.py``.

Nace de extraer el Tarjan que ``check_addon_cycles.py`` tenia en su cuerpo:
``orden_de_porte.py`` necesita el mismo recorrido, y copiarlo habria creado
la segunda fuente de verdad que ``calibration-verified-numbers.md`` prohibe.

Por que Tarjan y no Kosaraju
=============================

Kosaraju es mas facil de explicar —dos recorridos en profundidad— pero
necesita el grafo invertido y dos pasadas. Tarjan hace una sola, y sobre
todo: **ya existia en este arbol, iterativo y con su gate corriendo**. Reusar
codigo probado gana a reescribir uno mas didactico cuando el criterio de
mayor peso es el tiempo de desarrollo y el de menor es el rendimiento.

El reparto de criterios que decide esto —y las dos decisiones compartidas con
los otros dos modulos, no traer ``networkx`` y consultar la forma de
``cytoscape.js`` sin instalarlo— vive en el hallazgo de la tarea #217, no
repetido aqui: una decision con tres copias divergiria sin que nadie lo note.

**Iterativo, no recursivo, y no es preferencia.** Con Tarjan recursivo una
cadena de mas de mil nodos levanta ``RecursionError`` — el limite por defecto
de Python. Lo mide ``test_it_does_not_recurse_on_a_long_chain``.
"""


def strongly_connected_components(nodes, edges):
    """Tarjan iterativo — los componentes fuertemente conexos, todos.

    Iterativo y no recursivo porque un grafo de dependencias puede tener
    caminos mas largos que el limite de recursion de Python, y el fallo seria
    un ``RecursionError`` en vez de un resultado.

    :param nodes: iterable de nodos.
    :param edges: mapa nodo -> conjunto de nodos a los que apunta.
    :returns: lista de componentes, cada uno lista de nodos.
    """
    index, low, on_stack, stack, counter, output = {}, {}, {}, [], [0], []

    def walk(start):
        work = [(start, 0)]
        while work:
            node, i = work[-1]
            if i == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            descended = False
            neighbours = sorted(edges.get(node, ()))
            for j in range(i, len(neighbours)):
                neighbour = neighbours[j]
                if neighbour not in index:
                    work[-1] = (node, j + 1)
                    work.append((neighbour, 0))
                    descended = True
                    break
                if on_stack.get(neighbour):
                    low[node] = min(low[node], index[neighbour])
            if descended:
                continue
            if low[node] == index[node]:
                component = []
                while True:
                    popped = stack.pop()
                    on_stack[popped] = False
                    component.append(popped)
                    if popped == node:
                        break
                output.append(component)
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])

    for node in nodes:
        if node not in index:
            walk(node)
    return output



def cyclic_components(nodes, edges):
    """Solo los componentes de mas de un nodo — los ciclos reales.

    Un componente de un nodo es un nodo suelto, no un ciclo; salvo que apunte
    a si mismo, y ese caso se comprueba explicitamente en vez de suponerlo.
    """
    components = strongly_connected_components(nodes, edges)
    return [c for c in components
            if len(c) > 1 or c[0] in edges.get(c[0], ())]


