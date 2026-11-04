#!/usr/bin/env python3
"""Una frontera vacía no es aceptación: población de la iniciativa y plan.

El defecto que cierra
=====================

``continuation_frontier.runnable_items`` sólo lee ``plan.jsonl``: no sabe qué
TASK nativas tiene la iniciativa. Al asentarse TASK-API-0417 la frontera quedó
vacía con TASK-API-0418 pendiente, y nada lo distinguía de una iniciativa
terminada. El productor que llevaría las TASK del store al plan es del
proveedor (H-THYROX-697, TASK-THYROX-1112); mientras no exista, este banco
declara en su ``manifest.json`` que es ciego al trabajo hecho fuera del plan.
Esta sonda convierte esa ceguera en un dictamen medible.

Las tres situaciones, y ninguna es ACCEPTED
===========================================

- **A** — ninguna TASK de la población abierta ni ninguna unidad abierta. Es un
  candidato: la aceptación la autoriza el ejecutor (I-011), no este conteo.
- **B** — hay trabajo pendiente y al menos una unidad admisible.
- **C** — hay trabajo pendiente y nada admisible. Se nombra por qué: unidades
  bloqueadas (con su razón), TASK sin unidad en el plan (``unrepresented``) o
  TASK cuyas unidades ya se asentaron pero que sigue abierta en el store
  (``settled_task_open``: pide cierre o un tramo nuevo, no reimplementar).

Reusa, no redefine
==================

La población es la de
``task-responsibility-view-20261103/responsibility_view.py``
(las citas de los ``.rst`` de la iniciativa, sin las del proveedor) y el estado
nativo, el del store por su lectura de sólo lectura. El plan, el registro, los
estados y la frontera son los del proveedor: ``load_plan``, ``read_log``,
``item_states`` y ``runnable_items``.

*Métrica:* TASK de la población con estado nativo abierto, cruzadas con las
unidades de ``plan.jsonl`` por ``taskId`` y con su estado en
``outputs/continuation.jsonl``.
*Ciega a:* una obligación contractual que ninguna TASK nombra todavía —la
población es la de las citas, no la del inventario por símbolo—, y a una cita
de la iniciativa que no esté escrita como ``TASK-<CAPA>-NNNN``.
"""
import argparse
import importlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE.parent
HOME = pathlib.Path('/home/user')
THYROX = HOME / 'thyrox'
VIEW = BENCH.parent / 'task-responsibility-view-20261103'
sys.path.insert(0, str(THYROX / 'src'))
sys.path.insert(0, str(VIEW))

view = importlib.import_module('responsibility_view')
frontier_module = importlib.import_module('session.continuation_frontier')
controller = importlib.import_module('session.task_continuation')
INITIATIVE = (HOME / 'kaupamex-docs/source/gestion/pm/api/iniciativas'
              / 'completar-raiz-orm')
STORE = THYROX / 'agent-results/agent_store.sqlite3'

OPEN_STATUSES = ('pending', 'in_progress')
ACCEPTANCE = 'requires executor authority (I-011)'


def blocking_reason(unit, states):
    """Por qué una unidad no asentada no está en la frontera."""
    state = states.get(unit.id)
    if state is not None:
        return f'state {state}'
    waiting = [dep for dep in unit.depends_on if states.get(dep) != 'accepted']
    if waiting:
        return 'waits for ' + ', '.join(waiting)
    return 'conflicts with a unit in flight or ahead in the frontier'


def classify(population, plan, states):
    """El dictamen A/B/C sobre la población, el plan y sus estados."""
    frontier = frontier_module.runnable_items(plan, states)
    frontier_ids = {unit.id for unit in frontier}
    units_by_task = {}
    for unit in plan:
        units_by_task.setdefault(unit.task_id, []).append(unit)
    blocked = [
        {'id': unit.id, 'task': unit.task_id,
         'reason': blocking_reason(unit, states)}
        for unit in plan
        if unit.id not in frontier_ids and states.get(unit.id) != 'accepted'
    ]
    open_tasks = [row['citation'] for row in population
                  if row['native_status'] in OPEN_STATUSES]
    unrepresented, settled_task_open = [], []
    for citation in open_tasks:
        units = units_by_task.get(citation, [])
        if not units:
            unrepresented.append(citation)
        elif all(states.get(unit.id) == 'accepted' for unit in units):
            settled_task_open.append(citation)
    if not open_tasks and not blocked and not frontier:
        verdict = 'A'
    elif frontier:
        verdict = 'B'
    else:
        verdict = 'C'
    return {
        'verdict': verdict,
        'acceptance': ACCEPTANCE,
        'population': len(population),
        'open_tasks': len(open_tasks),
        'frontier': [{'id': unit.id, 'task': unit.task_id}
                     for unit in frontier],
        'blocked': blocked,
        'unrepresented': unrepresented,
        'settled_task_open': settled_task_open,
    }


def population_of(initiative, store):
    """La población de la vista de responsabilidad, con su estado nativo."""
    rows = view.store_rows(store)
    population = []
    for citation in sorted(view.sentences(initiative)):
        row = rows.get(citation)
        if view.is_provider(citation, row):
            continue
        population.append({
            'citation': citation,
            'native_status': row['status'] if row else 'not_verified'})
    return population


def report_for(bench, initiative=INITIATIVE, store=STORE):
    """El dictamen de un banco, o None si falta la iniciativa o el store."""
    if not initiative.is_dir() or not store.is_file():
        return None
    log = controller.read_log(bench)
    return classify(population_of(initiative, store),
                    controller.load_plan(bench),
                    frontier_module.item_states(log))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--bench', type=pathlib.Path, default=BENCH)
    parser.add_argument('--initiative', type=pathlib.Path, default=INITIATIVE)
    parser.add_argument('--store', type=pathlib.Path, default=STORE)
    args = parser.parse_args(argv)
    report = report_for(args.bench, args.initiative, args.store)
    if report is None:
        print('plan_coverage: no se puede medir — falta la iniciativa o el '
              'store; no se emite dictamen', file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return {'A': 0, 'B': 0, 'C': 1}[report['verdict']]


if __name__ == '__main__':
    raise SystemExit(main())
