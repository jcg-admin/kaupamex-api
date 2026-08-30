#!/usr/bin/env python3
"""Cuanto desbloquea cada nodo de un grafo dirigido.

Responsabilidad unica: **ponderar los nodos por cuantos caminos mas cortos
pasan por ellos**. No detecta ciclos ni secuencia nada; esas son las otras
dos preguntas (``graph_components.py``, ``graph_ordering.py``).

Por que Brandes y no PageRank ni el grado
==========================================

El **grado** cuenta vecinos directos, y la pregunta no es «a cuantos toca»
sino «por cuantos caminos pasa»: un simbolo puede tener un unico vecino y ser
el unico puente hacia veinte. Lo mide, y es el control que discrimina,
``test_the_bridge_beats_the_popular_node``.

**PageRank** responde algo parecido pero introduce dos perillas que habria
que justificar —factor de amortiguacion y criterio de convergencia— y cuyo
valor cambiaria el orden del porte sin que nada del grafo lo respalde.
Brandes no tiene ninguna: el valor sale del grafo y de nada mas.

El reparto de criterios que decide esto vive en el hallazgo de la tarea #217.
"""


def betweenness_centrality(nodes, edges):
    """Brandes — por cuantos caminos mas cortos pasa cada nodo.

    Responde «cuanto desbloquea este simbolo», que NO es lo mismo que «a
    cuantos toca»: un simbolo con un solo vecino puede ser el unico puente
    hacia veinte, y el grado no lo ve.

    Sin perillas: no hay factor de amortiguacion ni criterio de convergencia
    que justificar, a diferencia de PageRank. El valor sale del grafo y de
    nada mas.

    :returns: mapa nodo -> centralidad, sin normalizar. La escala no importa
        porque solo se usa para ordenar.
    """
    centrality = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack, predecessors = [], {n: [] for n in nodes}
        shortest = dict.fromkeys(nodes, 0.0)
        shortest[source] = 1.0
        distance = dict.fromkeys(nodes, -1)
        distance[source] = 0
        queue = [source]
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            stack.append(node)
            for neighbour in sorted(edges.get(node, ())):
                if neighbour not in distance:
                    continue
                if distance[neighbour] < 0:
                    distance[neighbour] = distance[node] + 1
                    queue.append(neighbour)
                if distance[neighbour] == distance[node] + 1:
                    shortest[neighbour] += shortest[node]
                    predecessors[neighbour].append(node)
        dependency = dict.fromkeys(nodes, 0.0)
        while stack:
            node = stack.pop()
            for predecessor in predecessors[node]:
                dependency[predecessor] += (
                    shortest[predecessor] / shortest[node]
                    * (1 + dependency[node]))
            if node != source:
                centrality[node] += dependency[node]
    return centrality
