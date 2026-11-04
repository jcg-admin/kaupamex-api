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

- **A** — ninguna TASK de la población abierta, ninguna unidad abierta y
  ninguna obligación del contrato pendiente. Es un candidato: la aceptación la
  autoriza el ejecutor (I-011), no este conteo.
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
Obligaciones del contrato
=========================

Las citas no son el contrato. El inventario estructural por tipo
(``orm-symbol-presence-census-20260910T175850/outputs/inventory_by_kind.tsv``)
clasifica cada símbolo de la referencia como ``satisfied``, ``absent``,
``divergent`` o ``not_verified``. Una obligación pendiente —cualquiera de las
tres últimas— impide el dictamen A aunque ninguna TASK quede abierta y la
frontera esté vacía. Las que no nombran TASK (columna opcional ``task``) se
publican agrupadas por módulo en ``obligations_without_task``: son trabajo que
el plan no puede seleccionar porque nadie lo ha convertido en TASK.

*Métrica:* TASK de la población con estado nativo abierto, cruzadas con las
unidades de ``plan.jsonl`` por ``taskId`` y con su estado en
``outputs/continuation.jsonl``; y filas del inventario por categoría.
*Ciega a:* una cita de la iniciativa que no esté escrita como
``TASK-<CAPA>-NNNN``; a la vigencia del inventario, que es la del commit en que
se generó (se publica en ``obligations.source``); y a una obligación que el
inventario no enumera —atributos de instancia, comportamiento sin caso—.
"""
import argparse
import collections
import csv
import importlib
import json
import pathlib
import re
import sqlite3
import subprocess
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
claim_fold = importlib.import_module('session.claim_fold')
in_flight = importlib.import_module('session.in_flight')
controller = importlib.import_module('session.task_continuation')
INITIATIVE = (HOME / 'kaupamex-docs/source/gestion/pm/api/iniciativas'
              / 'completar-raiz-orm')
STORE = THYROX / 'agent-results/agent_store.sqlite3'
INVENTORY = (BENCH.parent / 'orm-symbol-presence-census-20260910T175850'
             / 'outputs/inventory_by_kind.tsv')
REPO = BENCH.parents[2]
CONTRACTS = (REPO / 'scripts/evidence/orm-as-is-substantive-20261021T194156'
             / 'outputs/contractual-assessments.json')
CLAIMS = REPO / '.claude/coordination/claims.jsonl'
INTEGRATION_REF = 'origin/feature/codex-workspace-bootstrap'
NODE = 'x2hokp'

OPEN_STATUSES = ('pending', 'in_progress')
CATEGORIES = ('satisfied', 'absent', 'divergent', 'not_verified')
PENDING_CATEGORIES = CATEGORIES[1:]
ACCEPTANCE = 'requires executor authority (I-011)'


def foreign_claims(claims_rows, node):
    """Los claims activos de OTROS dueños, como los ve ``next_for_node``.

    Mismas primitivas que ``thyrox: src/session/node_next_task.py``: el
    pliegue de ``claim_fold`` y el dueño propio de ``in_flight.own_owner``.
    """
    mine = in_flight.own_owner(node)
    return [
        {'path': claim_fold.normalize_claim_path(claim['path']),
         'owner': claim['owner'], 'task': claim.get('task')}
        for claim in claim_fold.active_claims(claims_rows)
        if claim['owner'].lower() != mine
    ]


def claim_conflict(unit, foreign):
    """El primer claim ajeno que se solapa con lo que la unidad declara."""
    owned = tuple(claim_fold.normalize_claim_path(path)
                  for path in unit.owned)
    for claim in foreign:
        if owned and frontier_module._overlaps(owned, (claim['path'],)):
            return claim
    return None


def blocking_reason(unit, states, foreign=()):
    """Por qué una unidad no asentada no está en la frontera."""
    claim = claim_conflict(unit, foreign)
    if claim is not None:
        return (f"claimed by {claim['owner']} ({claim['task']}) on "
                f"{claim['path']}")
    state = states.get(unit.id)
    if state is not None:
        return f'state {state}'
    waiting = [dep for dep in unit.depends_on if states.get(dep) != 'accepted']
    if waiting:
        return 'waits for ' + ', '.join(waiting)
    return 'conflicts with a unit in flight or ahead in the frontier'


def obligation_summary(obligations, open_citations):
    """Conteo por categoría y pendientes sin TASK abierta, por módulo.

    Una obligación cuya TASK está cerrada sigue pendiente si su categoría lo
    está: cerrar la TASK no satisface el contrato.
    """
    counts = collections.Counter(row['category'] for row in obligations)
    unknown = set(counts) - set(CATEGORIES)
    if unknown:
        raise ValueError(f'categoría desconocida: {sorted(unknown)}')
    without_task = collections.Counter(
        row['module'] for row in obligations
        if row['category'] in PENDING_CATEGORIES
        and row.get('task') not in open_citations)
    summary = {category: counts.get(category, 0) for category in CATEGORIES}
    summary['applicable'] = len(obligations)
    summary['pending'] = sum(summary[c] for c in PENDING_CATEGORIES)
    return summary, dict(sorted(without_task.items()))


def obligation_key(row):
    """La identidad de una obligación en obligations de una unidad."""
    return f"{row['module']}::{row['symbol']}"


#: Dónde vive la prueba roja de una obligación, por raíz espejo. Una raíz sin
#: entrada no produce candidatas: su convención de prueba no está decidida.
TEST_HOMES = {'src/orm/': 'tests/integration/test_orm'}
VERIFY = 'uv run pytest -q --reuse-db -p no:cacheprovider {test}'


def symbol_slug(symbol, kind):
    """El tramo del id y del archivo de prueba que nombra una obligación.

    Distingue lo que el minúsculo y el guion bajo colapsarían: cada guion bajo
    inicial de un componente se marca con ``p`` (``_f`` y ``f`` son
    obligaciones distintas, y la visibilidad es contrato), cada guion bajo
    final con ``t`` (``_fields`` frente a ``_fields__``), y un tipo que no es
    método añade su nombre (``Command.CREATE`` frente a ``Command.create``).
    """
    parts = []
    for part in symbol.split('.'):
        bare = part.strip('_')
        hidden = len(part) - len(part.lstrip('_'))
        trailing = len(part) - len(part.rstrip('_'))
        parts.append('_'.join(filter(None, (
            'p' * hidden, bare.lower(), 't' * trailing))))
    slug = re.sub(r'_+', '_', '_'.join(parts)).strip('_')
    return slug if kind == 'method' else f'{slug}_{kind}'


def candidate_rows(rows):
    """Las filas candidatas del plan: una por obligación pendiente que su
    TASK de alcance todavía no representa con una unidad.

    Es la traducción del consumidor —qué prueba, qué ruta, qué verify—; qué
    candidata entra y cuándo lo decide local_plan supply del proveedor.
    """
    candidates = []
    for row in rows:
        home = next((test for root, test in TEST_HOMES.items()
                     if row['module'].startswith(root)), None)
        if (row.get('operational_class') != 'task_without_unit'
                or not row.get('symbol') or home is None):
            continue
        task = row['linked_tasks'][0]
        stem = row['module'].rsplit('/', 1)[1].removesuffix('.py')
        slug = symbol_slug(row['symbol'], row['kind'])
        test = f'{home}/test_contract_{stem}_{slug}.py'
        candidates.append({
            'id': f"{stem}-{slug.replace('_', '-')}-{task[-4:]}",
            'taskId': task, 'candidates': ['claude-opus-5-5'],
            'owned': [row['module'], test], 'dependsOn': [],
            'obligations': [obligation_key(row)],
            'verify': VERIFY.format(test=test),
            'prompt': (f"Portar {row['kind']} {row['symbol']} de "
                       f"{row['module']} conforme a odoo19c; la prueba roja "
                       f"vive en {test}."),
        })
    return candidates


def obligation_class(row, open_citations, units_by_task, states,
                     frontier_ids, links, candidates, scopes, carried=None):
    """La situación operativa de UNA obligación pendiente.

    El vínculo explícito sale de la columna ``task`` del inventario o de los
    ``task_links`` de un descriptor funcional; el candidato, de una TASK
    abierta del store que nombra el archivo y el símbolo. Un candidato NO
    cuenta como representación: sigue en ``obligations_without_task``.
    """
    explicit = set(links.get((row['module'], row['symbol']), ()))
    if row.get('task'):
        explicit.add(row['task'])
    by_scope = not explicit
    if by_scope:
        explicit = set(scopes.get(row['module'].rsplit('/', 1)[0], ()))
    if explicit:
        live = explicit & open_citations
        if not live:
            return 'task_closed', sorted(explicit)
        units = [unit for task in live for unit in units_by_task.get(task, ())]
        if by_scope:
            # Una TASK de alcance agrupa todo un directorio: sólo la
            # representa, para ESTA obligación, la unidad que la lleva.
            key = obligation_key(row)
            units = [unit for unit in units
                     if key in (carried or {}).get(unit.id, ())]
        if not units:
            return 'task_without_unit', sorted(live)
        if all(states.get(unit.id) == 'accepted' for unit in units):
            return 'task_units_settled', sorted(live)
        if any(unit.id in frontier_ids for unit in units):
            return 'task_with_admissible_unit', sorted(live)
        return 'task_with_blocked_unit', sorted(live)
    found = candidates(row)
    if found:
        return 'candidate_task', sorted(found)
    return 'unrepresented', []


def classify(population, plan, states, obligations=(), foreign=(),
             integrated=None, links=None, candidates=None, scopes=None,
             store_open=None, carried=None):
    """El dictamen A/B/C sobre la población, el plan, sus estados y el
    contrato.

    ``foreign`` son los claims de otros dueños: una unidad cuyo ``owned`` se
    solapa con uno sale de la frontera con esa razón. ``integrated`` es el
    conjunto de unidades cuyo commit de asiento ya está en la rama de
    integración; ``None`` si no se pudo medir. ``scopes`` mapea un directorio
    espejo a la TASK que declara sus pendientes; ``store_open`` es el estado
    abierto NATIVO, que gana a las citas de docs para decidir si una TASK
    vinculada sigue viva.
    """
    links = links or {}
    scopes = scopes or {}
    candidates = candidates or (lambda row: set())
    # Lo reclamado por otro dueño se aparta ANTES de calcular la frontera: en
    # el mismo checkout dos unidades que mutan se serializan, y una unidad
    # bloqueada que siguiera en el cálculo taparía a la independiente que va
    # detrás.
    claimed = {unit.id for unit in plan
               if states.get(unit.id) is None
               and claim_conflict(unit, foreign) is not None}
    frontier = frontier_module.runnable_items(
        [unit for unit in plan if unit.id not in claimed], states)
    frontier_ids = {unit.id for unit in frontier}
    units_by_task = {}
    for unit in plan:
        units_by_task.setdefault(unit.task_id, []).append(unit)
    blocked = [
        {'id': unit.id, 'task': unit.task_id,
         'reason': blocking_reason(unit, states, foreign)}
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
    obligations = [dict(row) for row in obligations]
    classes = collections.Counter()
    open_citations = set(open_tasks) | set(store_open or ())
    for row in obligations:
        if row['category'] not in PENDING_CATEGORIES:
            continue
        kind, tasks = obligation_class(row, open_citations, units_by_task,
                                       states, frontier_ids, links,
                                       candidates, scopes, carried)
        row['operational_class'], row['linked_tasks'] = kind, tasks
        row['candidate_tasks'] = sorted(candidates(row))
        classes[kind] += 1
        if kind.startswith('task_') and kind != 'task_closed':
            row['task'] = tasks[0]
    summary, without_task = obligation_summary(obligations, open_citations)
    settled_not_integrated = (
        None if integrated is None else
        [unit.id for unit in plan
         if states.get(unit.id) == 'accepted' and unit.id not in integrated])
    if (not open_tasks and not blocked and not frontier
            and not summary['pending']):
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
        'obligations': summary,
        'obligations_without_task': without_task,
        'obligation_classes': dict(sorted(classes.items())),
        'settled_not_integrated': settled_not_integrated,
        'obligation_rows': [row for row in obligations
                            if 'operational_class' in row],
    }


def load_obligations(path=INVENTORY):
    """Las filas del inventario estructural, o None si no existe."""
    if not path.is_file():
        return None
    with path.open(encoding='utf-8') as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


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


def descriptor_links(path=CONTRACTS):
    """``(módulo, símbolo) -> TASK`` declarados por los descriptores
    funcionales.

    La autoridad es ``contractual-assessments.json``: cada descriptor nombra
    su ``reference_symbol`` (``odoo/orm/models.py::BaseModel.ensure_one:5931``)
    y sus ``task_links``. El módulo de la referencia se traduce a su espejo
    (``odoo/`` -> ``src/``) y se descarta el sufijo de línea. Los descriptores
    que citan pruebas de la referencia y no un símbolo no aportan vínculo
    estructural.
    """
    links = {}
    if not path.is_file():
        return links
    for entry in json.loads(path.read_text(encoding='utf-8'))['descriptors']:
        contract = entry['reference_contract_14_elements']
        references = contract['reference_symbol']
        if not isinstance(references, str):
            continue
        for reference in references.split(';'):
            if '::' not in reference:
                continue
            module, symbol = reference.strip().split('::', 1)
            key = (re.sub(r'^odoo/', 'src/', module),
                   re.sub(r':[\d,-]+$', '', symbol).strip())
            links.setdefault(key, set()).update(entry['task_links'])
    return links


#: El asunto con que una TASK declara como suyos los pendientes de un
#: directorio espejo. Es una declaración exacta del store, no una inferencia.
SCOPE_SUBJECT = re.compile(
    r'^Cerrar las obligaciones estructurales pendientes de (src(?:/[\w.]+)*)$')


def open_store_tasks(store):
    """``(cita, asunto, texto)`` de las TASK abiertas del store."""
    connection = sqlite3.connect(f'file:{store}?mode=ro', uri=True)
    return [
        (citation, subject, f"{subject} {description or ''}")
        for citation, status, subject, description in connection.execute(
            'select coalesce(layer_citation_id, citation_id), status, '
            'subject, description from tasks')
        if citation and status in OPEN_STATUSES]


def scope_links(tasks):
    """``directorio espejo -> {TASK}`` declarados por asunto."""
    scopes = {}
    for citation, subject, _text in tasks:
        match = SCOPE_SUBJECT.match(subject or '')
        if match:
            scopes.setdefault(match.group(1), set()).add(citation)
    return scopes


def store_candidates(store):
    """Función ``fila -> TASK abiertas`` que nombran su archivo y su
    símbolo.

    Lee el texto NATIVO del store (asunto y descripción), no las citas de
    docs. Un candidato no es un vínculo: sólo dice dónde mirar.
    """
    texts = [(citation, text)
             for citation, _subject, text in open_store_tasks(store)]

    def candidates(row):
        leaf = (row['symbol'] or '').split('.')[-1]
        base = row['module'].split('/')[-1]
        if len(leaf) < 5:
            return set()
        return {citation for citation, text in texts
                if leaf in text and base in text}
    return candidates


def integrated_units(bench, plan, states, ref=INTEGRATION_REF):
    """Unidades asentadas cuyo commit de asiento está en ``ref``.

    ``None`` si ``ref`` no se puede resolver: no medir no es «integrado».
    """
    if subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--verify',
                       '--quiet', ref], capture_output=True).returncode:
        return None
    commits = {}
    for row in controller.read_log(bench):
        if row.get('kind') == 'accepted' and row.get('commit'):
            commits[row['item']] = row['commit']
    done = set()
    for unit in plan:
        commit = commits.get(unit.id)
        if states.get(unit.id) == 'accepted' and commit and not subprocess.run(
                ['git', '-C', str(REPO), 'merge-base', '--is-ancestor',
                 commit, ref], capture_output=True).returncode:
            done.add(unit.id)
    return done


def load_claims(path=CLAIMS):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


CLASSIFICATION_COLUMNS = ('revision', 'module', 'symbol', 'kind', 'category',
                          'operational_class', 'linked_tasks',
                          'candidate_tasks', 'reason')


def write_classification(path, rows):
    """Una fila por obligación pendiente: su identidad, su estado
    contractual y su situación operativa. Es una salida regenerable, no una
    autoridad: se reescribe entera en cada ejecución."""
    with path.open('w', encoding='utf-8', newline='') as handle:
        handle.write('\t'.join(CLASSIFICATION_COLUMNS) + '\n')
        for row in rows:
            values = dict(row, linked_tasks=','.join(row['linked_tasks']),
                          candidate_tasks=','.join(row['candidate_tasks']))
            handle.write('\t'.join(str(values.get(column, ''))
                                   for column in CLASSIFICATION_COLUMNS)
                         + '\n')


def carried_obligations(bench):
    """Las obligations que declara cada unidad del plan, por id."""
    path = bench / 'plan.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()] if path.is_file() else []
    return {row['id']: set(row.get('obligations', ())) for row in rows}


def report_for(bench, initiative=INITIATIVE, store=STORE,
               inventory=INVENTORY, node=NODE):
    """El dictamen de un banco, o None si falta la iniciativa, el store o el
    inventario: sin cualquiera de los tres no se puede medir."""
    obligations = load_obligations(inventory)
    if not initiative.is_dir() or not store.is_file() or obligations is None:
        return None
    log = controller.read_log(bench)
    plan = controller.load_plan(bench)
    states = frontier_module.item_states(log)
    report = classify(population_of(initiative, store), plan, states,
                      obligations, foreign_claims(load_claims(), node),
                      integrated_units(bench, plan, states),
                      descriptor_links(), store_candidates(store),
                      scope_links(open_store_tasks(store)),
                      {row[0] for row in open_store_tasks(store)},
                      carried_obligations(bench))
    report['obligations']['source'] = {
        'path': str(inventory),
        'revisions': sorted({row['revision'] for row in obligations})}
    report['integration_ref'] = INTEGRATION_REF
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--bench', type=pathlib.Path, default=BENCH)
    parser.add_argument('--initiative', type=pathlib.Path, default=INITIATIVE)
    parser.add_argument('--store', type=pathlib.Path, default=STORE)
    parser.add_argument('--inventory', type=pathlib.Path, default=INVENTORY)
    parser.add_argument(
        '--classification', type=pathlib.Path, default=None,
        help='TSV con la clase operativa de cada obligación pendiente')
    parser.add_argument(
        '--candidates', type=pathlib.Path, default=None,
        help='JSON Lines con una fila candidata por obligación sin unidad')
    args = parser.parse_args(argv)
    report = report_for(args.bench, args.initiative, args.store,
                        args.inventory)
    rows = report.pop('obligation_rows', []) if report else []
    if report is None:
        print('plan_coverage: no se puede medir — falta la iniciativa, el '
              'store o el inventario; no se emite dictamen', file=sys.stderr)
        return 2
    if args.classification is not None:
        write_classification(args.classification, rows)
    if args.candidates is not None:
        args.candidates.write_text(''.join(
            json.dumps(row, ensure_ascii=False) + '\n'
            for row in candidate_rows(rows)))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return {'A': 0, 'B': 0, 'C': 1}[report['verdict']]


if __name__ == '__main__':
    raise SystemExit(main())
