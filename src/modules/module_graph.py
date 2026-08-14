"""Grafo de dependencias entre addons — fiel a ``odoo/modules/module_graph.py``.

Resuelve el **primero** de los tres grafos del proyecto (H-API-228): el de
addons-código, declarado en ``__manifest__.py:depends``.

Conserva de la referencia: ``ModuleNode`` con ``depends``/``depth``, el orden de
iteración por ``(depth, name)`` —que es el orden topológico de carga— y
``ModuleGraph.extend()`` como forma de poblarlo transitivamente.

**Divergencias deliberadas:**

- Sin cursor ni ``mode='load'|'update'``: la referencia lee el estado
  ``installed``/``to upgrade`` de ``ir_module_module`` para decidir qué cargar.
  Aquí no hay install dinámico (ver ``modules/__init__``), así que
  ``_update_from_database`` no se porta y el grafo es puramente estático.
- ``phase`` y ``demo_installable`` no se portan: sirven al instalador.
- Se añade ``cycles()``, que **no** está en la referencia. Odoo no lo necesita
  porque su grafo se puebla en orden de instalación y un ciclo se manifiesta
  como dependencia irresoluble; aquí el grafo se construye sobre un árbol ya
  escrito, donde un ciclo declarado es un defecto que hay que poder nombrar.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator

from modules.module import get_module_path, get_modules, load_manifest


class ModuleNode:
    """Un addon dentro del grafo. ≙ ``ModuleNode`` de la referencia."""

    __slots__ = ('name', '_graph', 'depends', 'manifest')

    def __init__(self, name: str, module_graph: ModuleGraph) -> None:
        self.name = name
        self._graph = module_graph
        self.manifest = load_manifest(name)
        self.depends: list[str] = list(self.manifest.get('depends', ()))

    @property
    def depth(self) -> int:
        """Profundidad = 1 + la máxima de sus dependencias presentes. ≙ referencia.

        Un addon sin ``depends`` (o cuyas dependencias no están en el grafo)
        tiene profundidad 0. Ordenar por ``depth`` da el orden topológico.
        """
        depths = [
            self._graph[d].depth
            for d in self.depends
            if d in self._graph and d != self.name
        ]
        return 1 + max(depths) if depths else 0

    @property
    def order_name(self) -> str:
        """Clave de orden estable. ≙ referencia."""
        return f'{self.depth:03d}-{self.name}'

    def __repr__(self) -> str:
        return f'ModuleNode({self.name!r}, depth={self.depth})'


class ModuleGraph:
    """Grafo de addons ordenable topológicamente. ≙ ``ModuleGraph`` de la referencia."""

    def __init__(self) -> None:
        self._nodes: dict[str, ModuleNode] = {}

    def __contains__(self, name: str) -> bool:
        return name in self._nodes

    def __getitem__(self, name: str) -> ModuleNode:
        return self._nodes[name]

    def __iter__(self) -> Iterator[ModuleNode]:
        """Itera en orden topológico: por ``(depth, name)``. ≙ referencia."""
        return iter(sorted(self._nodes.values(), key=lambda n: (n.depth, n.name)))

    def __len__(self) -> int:
        return len(self._nodes)

    def extend(self, names: Collection[str]) -> None:
        """Añade los addons y, transitivamente, sus ``depends``. ≙ referencia."""
        pending = list(names)
        seen: set[str] = set()
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            if name not in self._nodes:
                self._nodes[name] = ModuleNode(name, self)
            pending.extend(
                d for d in self._nodes[name].depends if d not in seen
            )

    def missing(self) -> dict[str, list[str]]:
        """``{addon: [deps declaradas cuyo addon NO existe en el árbol]}``.

        No está en la referencia: allí una dependencia ausente aborta la carga.
        Aquí el árbol ya está escrito, así que interesa *reportar* el hueco sin
        abortar.

        El criterio es la **existencia del addon**
        (``get_module_path() is None``), no la del manifest: hoy 58 de 59 addons
        no tienen manifest y son perfectamente reales. Confundir "no declara
        manifest" con "no existe" haría que este método señalara casi todo el
        árbol — la ceguera de instrumento de ``metrica-decide-la-conclusion``.
        """
        out = {}
        for node in self._nodes.values():
            absent = [d for d in node.depends if get_module_path(d) is None]
            if absent:
                out[node.name] = absent
        return out

    def cycles(self) -> list[list[str]]:
        """Ciclos en el grafo **declarado** (ver docstring del módulo)."""
        found: list[list[str]] = []
        WHITE, GREY, BLACK = 0, 1, 2
        color = dict.fromkeys(self._nodes, WHITE)

        def walk(name: str, stack: list[str]) -> None:
            color[name] = GREY
            stack.append(name)
            for dep in self._nodes[name].depends:
                if dep not in color:
                    continue
                if color[dep] == GREY:
                    found.append(stack[stack.index(dep):] + [dep])
                elif color[dep] == WHITE:
                    walk(dep, stack)
            stack.pop()
            color[name] = BLACK

        for name in sorted(self._nodes):
            if color[name] == WHITE:
                walk(name, [])
        return found

    def auto_installable(self, present: Collection[str]) -> list[str]:
        """Addons que deben instalarse solos dado un conjunto ya presente.

        Porta el **algoritmo** de ``odoo/modules/db.py:91-124``, no su
        almacenamiento. Allí es un bucle de punto fijo sobre SQL contra
        ``ir_module_module``: seleccionar los ``auto_install`` cuyas
        dependencias requeridas ya están marcadas ``to install``, marcarlos, y
        repetir hasta que no cambie nada. La lógica es de **grafo**; la tabla
        es sólo cómo Odoo la persiste, y ahí no hay nada que portar porque este
        árbol no tiene install dinámico.

        Es el mecanismo por el que la referencia instala **sola** cada addon
        puente: ``auth_totp_portal`` declara ``auto_install: True`` y
        ``depends: ['portal', 'auth_totp']``, así que aparece en cuanto sus dos
        lados existen. Sin esto, la separación backoffice/portal habría que
        cablearla a mano en cada despliegue.

        ``auto_install`` admite dos formas, fiel a la referencia
        (``db.py:82``): ``True`` (todas las ``depends`` son requeridas) o una
        colección de nombres (sólo ésos lo son — el resto puede faltar).

        :param present: addons ya presentes/activos.
        :return: addons a auto-instalar, en orden topológico.
        """
        selected: set[str] = set(present)
        while True:
            newly_selected = []
            for node in self._nodes.values():
                if node.name in selected:
                    continue
                auto = node.manifest.get('auto_install', False)
                if not auto:
                    continue
                required = node.depends if auto is True else [
                    d for d in node.depends if d in auto
                ]
                if all(d in selected for d in required):
                    newly_selected.append(node.name)
            if not newly_selected:
                break
            selected.update(newly_selected)
        return [n.name for n in self if n.name in selected - set(present)]

    def order(self) -> list[str]:
        """Nombres en orden topológico de carga."""
        return [node.name for node in self]

    def __repr__(self) -> str:
        return f'ModuleGraph({len(self)} nodos)'


def build_graph(names: Iterable[str] | None = None) -> ModuleGraph:
    """Grafo con todos los addons del árbol (o los indicados)."""
    graph = ModuleGraph()
    graph.extend(list(names) if names is not None else get_modules())
    return graph
