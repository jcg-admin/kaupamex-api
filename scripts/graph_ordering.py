#!/usr/bin/env python3
"""La secuencia sin bloqueos de un grafo dirigido — que se puede hacer ya.

Responsabilidad unica: **repartir los nodos en niveles**, donde el nivel N es
lo que ya no depende de nada pendiente. No decide que es un ciclo —eso lo
responde ``graph_components.py``— ni pondera cual conviene primero dentro de
un nivel —eso es ``graph_centrality.py``.

Por que Kahn y no el topologico por recorrido en profundidad
=============================================================

Los dos son ``O(V+E)`` y los dos dan un orden valido. Kahn gana en claridad
para ESTA pregunta porque **su estado ES la respuesta**: en cada paso, los
nodos con contador en cero son exactamente los que no tienen dependencia
pendiente. Un topologico por profundidad devuelve el mismo orden y no deja
ver los niveles, que es justo lo que se busca — no «el orden», sino «que
puedo hacer en paralelo ahora».

El reparto de criterios que decide esto vive en el hallazgo de la tarea #217.

Un ciclo NO se ordena: se devuelve aparte. Fingir un orden interno donde no
lo hay es peor que declarar que no lo hay, porque el consumidor no puede
distinguir un orden real de uno inventado.
"""


def topological_levels(nodes, edges):
    """Kahn por niveles — cada nivel es lo que ya no tiene bloqueos.

    Devuelve una lista de niveles; el nivel N son los nodos cuyas
    dependencias estan todas en niveles anteriores. Es la forma que responde
    a la pregunta del porte: *que puedo hacer ahora sin chocar*.

    Los nodos que quedan en un ciclo NO aparecen: un ciclo no tiene orden
    interno, y fingir uno seria peor que declararlo. Se devuelven aparte.

    :returns: ``(niveles, atrapados_en_ciclo)``.
    """
    nodes = list(nodes)
    pending = {n: len({d for d in edges.get(n, ()) if d in set(nodes)})
               for n in nodes}
    dependents = {n: set() for n in nodes}
    for node in nodes:
        for dependency in edges.get(node, ()):
            if dependency in dependents:
                dependents[dependency].add(node)

    levels, placed = [], set()
    while True:
        level = sorted(n for n in nodes
                       if n not in placed and pending[n] == 0)
        if not level:
            break
        levels.append(level)
        placed.update(level)
        for node in level:
            for dependent in dependents[node]:
                pending[dependent] -= 1
    return levels, sorted(set(nodes) - placed)


