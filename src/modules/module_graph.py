"""Grafo de dependencias entre addons — fiel a ``odoo/modules/module_graph.py``.

Resuelve el **primero** de los tres grafos del proyecto (H-API-228): el de
addons-código, declarado en ``__manifest__.py:depends``.

Conserva nodos y orden por profundidad y clave de dependencia: los addons
``test_*`` comparten profundidad con su última dependencia y la siguen antes
de sus dependientes ordinarios. ``extend`` añade dependencias transitivas.

Contratos de ejecución todavía pendientes bajo TASK-API-0382:

- Sin cursor ni ``mode='load'|'update'``: la referencia lee el estado
  ``installed``/``to upgrade`` de ``ir_module_module`` para decidir qué cargar.
  El catálogo y las solicitudes administrativas ya persisten por base;
  el grafo todavía no consume esos estados ni ejecuta las solicitudes.
  Fases y elegibilidad demo operan sobre el estado explícito de sus nodos;
  falta enlazarlo al contexto persistente de carga.
- ``cycles()`` permite diagnosticar dependencias cíclicas; ordenar un ciclo
  lanza ModuleGraphCycle. La referencia elimina los nodos afectados al fallar
  su cálculo de profundidad; esa política de poda sigue siendo otro contrato.
"""
from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator
import logging

from modules.module import get_module_path, get_modules, load_manifest

_logger = logging.getLogger(__name__)


class ModuleGraphCycle(ValueError):
    """Dependencias cíclicas: no existe un orden válido de carga."""

    def __init__(self, cycle):
        self.cycle = tuple(cycle)
        super().__init__('ModuleGraphCycle: ' + ' -> '.join(self.cycle))


class ModuleNode:
    """Un addon dentro del grafo. ≙ ``ModuleNode`` de la referencia."""

    __slots__ = ('name', '_graph', 'depends', 'manifest', 'demo', 'state')

    def __init__(self, name: str, module_graph: ModuleGraph) -> None:
        self.name = name
        self._graph = module_graph
        self.manifest = load_manifest(name)
        self.depends: list[str] = list(self.manifest.get('depends', ()))
        self.demo = False
        self.state = 'uninstalled'

    @property
    def demo_installable(self) -> bool:
        """Los datos demo requieren demo habilitada en cada dependencia."""
        return all(self._graph[dep].demo for dep in self.depends)

    @property
    def phase(self) -> int:
        """Fase según el modo y las fronteras de instalación explícitas."""
        if self.name != 'base' and self._graph.mode == 'update':
            # Keep the existing explicit cycle diagnostic for recursive phases.
            self._graph._depth(self, {}, {})
        return self._graph._phase(self, {})

    @property
    def depth(self) -> int:
        """Distancia de carga; test_* comparte la de su última dependencia.

        Un addon ordinario sin dependencias presentes tiene profundidad0.
        Un test_* sin dependencia de anclaje rechaza el cálculo.
        """
        return self._graph._depth(self, {}, {})

    @property
    def order_name(self) -> str:
        """Clave de orden estable. ≙ referencia."""
        if self.name.startswith('test_'):
            # Validate the complete path before recursively resolving names;
            # a cycle must remain a domain error, not a RecursionError.
            _ = self.depth
            dependency = max(
                (self._graph[dep] for dep in self.depends if dep in self._graph),
                key=lambda node: (node.depth, node.order_name),
            )
            return dependency.order_name + ' ' + self.name
        return self.name

    def __repr__(self) -> str:
        return f'ModuleNode({self.name!r}, depth={self.depth})'


class ModuleGraph:
    """Grafo de addons ordenable topológicamente. ≙ ``ModuleGraph`` de la referencia."""

    def __init__(self, *, mode: str = 'load') -> None:
        if mode not in ('load', 'update'):
            raise ValueError('ModuleGraph mode must be load or update')
        self.mode = mode
        self._nodes: dict[str, ModuleNode] = {}

    def __contains__(self, name: str) -> bool:
        return name in self._nodes

    def __getitem__(self, name: str) -> ModuleNode:
        return self._nodes[name]

    def __iter__(self) -> Iterator[ModuleNode]:
        """Ordena por fase explícita, profundidad y clave de dependencia."""
        depths = {}
        phases = {}
        for name in sorted(self._nodes):
            self._depth(self._nodes[name], depths, {})
        for node in self._nodes.values():
            self._phase(node, phases)
        return iter(sorted(self._nodes.values(), key=lambda n: (
            phases[n.name], depths[n.name], n.order_name)))

    def _phase(self, node, memo):
        if node.name in memo:
            return memo[node.name]
        if node.name == 'base':
            phase = 0
        elif self.mode == 'load':
            phase = 1
        else:
            phase = max(
                self._phase(self._nodes[dep], memo)
                + int((node.state == 'to install') != (self._nodes[dep].state == 'to install'))
                + int(dep == 'base')
                for dep in node.depends
            )
        memo[node.name] = phase
        return phase

    def _depth(self, node, memo, path):
        if node.name in path:
            cycle = tuple(path)[path[node.name]:] + (node.name,)
            raise ModuleGraphCycle(cycle)
        if node.name in memo:
            return memo[node.name]
        path[node.name] = len(path)
        try:
            depths = [self._depth(self._nodes[dep], memo, path)
                      for dep in node.depends if dep in self._nodes]
            if node.name.startswith('test_'):
                # As in the pinned source, a test addon without dependencies
                # has no insertion anchor and max() raises ValueError.
                memo[node.name] = max(depths)
            else:
                memo[node.name] = 1 + max(depths) if depths else 0
            return memo[node.name]
        finally:
            del path[node.name]

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

    def _remove(self, name: str, log_dependents: bool = True) -> None:
        """Retira un nodo y sus dependientes del grafo que se está preparando.

        Adaptado de Odoo Community19, module_graph.py (LGPL-3). No cambia
        estados persistidos ni ejecuta una desinstalación. La preparación
        explícita usa esta poda; el grafo estático sigue rechazando ciclos.
        """
        self._nodes.pop(name)
        for another, node in list(self._nodes.items()):
            if name in node.depends and node.name in self._nodes:
                if log_dependents:
                    _logger.info(
                        'module %s: its direct/indirect dependency is skipped, skipped',
                        another,
                    )
                self._remove(another)

    def _update_depends(self, names: Iterable[str]) -> None:
        """Enlaza dependencias presentes y poda las que no pueden resolverse."""
        for name in names:
            node = self._nodes.get(name)
            if node is None:
                continue
            depends = node.manifest['depends']
            try:
                linked = [self._nodes[dep].name for dep in depends]
            except KeyError:
                missing = [dep for dep in depends if dep not in self._nodes]
                _logger.warning(
                    'module %s: some depends are not loaded (%s), skipped',
                    name, ', '.join(missing),
                )
                self._remove(name)
            else:
                node.depends = linked

    def _update_depth(self, names: Iterable[str]) -> None:
        """Poda ciclos en preparación explícita; no sustituye order/cycles."""
        for name in names:
            node = self._nodes.get(name)
            if node is None:
                continue
            try:
                _ = node.depth
            except (ModuleGraphCycle, RecursionError):
                _logger.warning('module %s: in a dependency loop, skipped', name)
                self._remove(name)

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
                if auto is False or not node.manifest.get('installable', True):
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
