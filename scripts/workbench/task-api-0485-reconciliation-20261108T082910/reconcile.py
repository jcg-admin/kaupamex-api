"""Reconcilia TASK-API-0485 contra el store, el plan y el inventario.

Mide, sin escribir en ninguna autoridad: la identidad del TASK en el store
del Provider (filas, citas duplicadas, publicación en ``origin``), sus
unidades en el plan con su aceptación y su modelo, y el destino de las
obligaciones que esas unidades nombran en la clasificación y el inventario.

Uso: reconcile.py <ruta-store-local> <ruta-store-origin> <salida.json>
"""
import collections
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
PLAN = ROOT / 'scripts/workbench/orm-continuation-plan-20261103T095630'
CENSUS = ROOT / 'scripts/workbench/orm-symbol-presence-census-20260910T175850'
TASK = 'TASK-API-0485'


def store_identity(path):
    """Filas del TASK, citas duplicadas y la cita API más alta del store."""
    connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    rows = connection.execute(
        'select task_id, session_id, board_ordinal, source, status, '
        'created_at from tasks where citation_id = ?', (TASK,)).fetchall()
    duplicates = connection.execute(
        'select citation_id from tasks where citation_id is not null '
        'group by citation_id having count(*) > 1').fetchall()
    highest = connection.execute(
        "select max(citation_id) from tasks "
        "where citation_id like 'TASK-API-%'").fetchone()[0]
    return {'rows': rows, 'duplicate_citations': len(duplicates),
            'highest_api_citation': highest}


def units():
    """Unidades del TASK, su aceptación, su modelo y sus obligaciones."""
    plan = [json.loads(line) for line in (PLAN / 'plan.jsonl').open()]
    accepted, models = set(), {}
    for line in (PLAN / 'outputs/continuation.jsonl').open():
        record = json.loads(line)
        if record['kind'] == 'accepted':
            accepted.add(record['item'])
        elif record['kind'] == 'attempt':
            models[record['item']] = record['model']
    mine = [unit for unit in plan if unit['taskId'] == TASK]
    obligations = {name for unit in mine
                   for name in unit.get('obligations', ())}
    return mine, accepted, models, obligations


def destinations(obligations):
    """Dónde cae cada obligación: clasificación pendiente o inventario."""
    classified = {}
    for line in (PLAN / 'outputs/obligation_classification.tsv').open():
        fields = line.rstrip('\n').split('\t')
        if len(fields) > 6:
            classified[f'{fields[1]}::{fields[2]}'] = fields[5]
    inventory = {}
    for line in (CENSUS / 'outputs/inventory_by_kind.tsv').open():
        fields = line.rstrip('\n').split('\t')
        if len(fields) > 4:
            inventory[f'{fields[1]}::{fields[2]}'] = fields[4]
    named = collections.Counter(
        classified.get(name) or 'inventory:' + inventory.get(
            name, 'outside_census')
        for name in obligations)
    task_rows = collections.Counter(
        state for (name, state) in classified.items()
        if name in obligations)
    pending = sum(1 for line in (PLAN / 'outputs/obligation_classification.tsv'
                                 ).open() if f'\t{TASK}\t' in line)
    return dict(named), dict(task_rows), pending


def main(local, origin, out):
    mine, accepted, models, obligations = units()
    named, _rows, pending = destinations(obligations)
    record = {
        'task': TASK,
        'store_local': store_identity(local),
        'store_origin': store_identity(origin),
        'units': len(mine),
        'units_accepted': sum(unit['id'] in accepted for unit in mine),
        'unit_models': dict(collections.Counter(
            models.get(unit['id'], '-') for unit in mine)),
        'obligations_named_by_units': len(obligations),
        'obligation_destinations': named,
        'classification_rows_for_task': pending,
    }
    pathlib.Path(out).write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:4])
