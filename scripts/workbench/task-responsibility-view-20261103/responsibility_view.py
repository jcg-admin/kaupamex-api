#!/usr/bin/env python3
"""Vista de responsabilidad de las TASK de una iniciativa, con seis ejes separados.

Universo
--------
Las citas durables ``TASK-<CAPA>-NNNN`` que aparecen en los ``.rst`` de la
iniciativa. Se excluyen las del PROVEEDOR: ``TASK-THYROX-*`` y las ``TASK-GEN``
cuya cita de capa es ``TASK-THYROX-*``.

Seis ejes, cada uno con su fuente y sin derivar uno de otro
-----------------------------------------------------------
``functional_role``   lo que la prosa de la iniciativa DECLARA en la misma
                      oracion que la cita («responsabilidad funcional backend»).
``verifier``          lo que la prosa declara como verificacion («verificacion qa»).
``operational_owner`` columna ``owner`` del store (asignacion por TaskUpdate).
``session_identity``  columna ``session_id`` del store.
``execution_identity`` quien ejecuto: el store no lo registra; sale de la
                      prosa (``owner`` + «ejecucion») si la declara.
``resource_claims``   filas del ledger ``.claude/coordination/claims.jsonl``
                      con ``task`` igual a la cita: activas (``active_claims``
                      de ``thyrox: src/session/claim_fold.py``) / historicas.
``approval_authority`` el ejecutor, por I-011 de ``thyrox-invariants.md``: es
                      regla, no observacion por tarea.

Un eje sin fuente se escribe ``not_verified``, nunca vacio ni cero. El estado
nativo (``pending``/``in_progress``/``completed``) se copia del store tal cual.

*Metrica:* filas del store por cita, oraciones de la iniciativa que contienen
la cita, mensajes de commit de api y docs que la nombran, filas del ledger.
*Ciega a:* una responsabilidad declarada en otra iniciativa o fuera de
``docs``; una oracion que nombra la tarea por su ordinal suelto («0283»); un
commit que hizo el trabajo sin nombrar la cita.
"""
import argparse
import collections
import json
import pathlib
import re
import sqlite3
import subprocess
import sys

HOME = pathlib.Path('/home/user')
THYROX = HOME / 'thyrox'
sys.path.insert(0, str(THYROX / 'src' / 'session'))
from claim_fold import active_claims  # noqa: E402

CITATION = re.compile(r'TASK-[A-Z]+-\d{4}')
ROLE = re.compile(r'responsabilidad(?: funcional)? (backend|devops|qa|ui|docs)')
VERIFIER = re.compile(r'verificaci[oó]n (backend|devops|qa|ui|docs)')
ROLES = ('backend', 'devops', 'qa', 'ui', 'docs')


def sentences(root):
    """``{cita: [oraciones]}`` de los ``.rst`` de la iniciativa."""
    found = collections.defaultdict(list)
    for path in sorted(root.rglob('*.rst')):
        text = ' '.join(path.read_text(encoding='utf-8').split())
        for sentence in re.split(r'(?<=[.])\s+', text):
            for citation in set(CITATION.findall(sentence)):
                found[citation].append(sentence)
    return found


def declared(pattern, texts):
    values = sorted({m.group(1) for t in texts for m in pattern.finditer(t)})
    return ','.join(values) if values else 'not_verified'


#: Propuesta por el ASUNTO de la tarea. Es inferencia, no declaracion, y vive
#: en su propia columna para no confundirse con ``functional_role``.
PROPOSAL = (
    ('devops', re.compile(r'\b(CI|gate|hook|pre-commit|ledger|despliegue|deploy)\b', re.I)),
    ('qa', re.compile(r'\b(suite|test|pruebas?|verificar|auditar|re-auditar|censar|medir)\b', re.I)),
    ('ui', re.compile(r'\b(ui|vista web|frontend)\b', re.I)),
)


def proposed_role(row):
    for role, pattern in PROPOSAL:
        if pattern.search(row['subject'] or ''):
            return f'{role} (inferido)'
    return 'backend (inferido)'


def store_rows(store):
    connection = sqlite3.connect(f'file:{store}?mode=ro', uri=True)
    rows = {}
    query = ('select citation_id, layer_citation_id, subject, status, owner, '
             'session_id, blocked_by_json from tasks')
    for citation, layer, subject, status, owner, session, blocked in connection.execute(query):
        record = {'layer': layer, 'subject': subject, 'status': status,
                  'owner': owner, 'session': session, 'blocked_by': blocked}
        for key in (citation, layer):
            if key:
                rows.setdefault(key, record)
    return rows


def claims_by_task(ledgers):
    rows = []
    for ledger in ledgers:
        if ledger.is_file():
            rows.extend(json.loads(line) for line in ledger.read_text().splitlines()
                        if line.strip())
    active = collections.Counter(r.get('task') for r in active_claims(rows))
    total = collections.Counter(r.get('task') for r in rows if r.get('op') == 'claim')
    return active, total


def commits_naming(citation, repos):
    count = 0
    for repo in repos:
        result = subprocess.run(['git', '-C', str(repo), 'log', '--all', '--format=%h',
                                 f'--grep={citation}'], capture_output=True, text=True)
        count += len(result.stdout.split())
    return count


def is_provider(citation, row):
    if citation.startswith('TASK-THYROX-'):
        return True
    return bool(row and (row.get('layer') or '').startswith('TASK-THYROX-'))


def build(initiative, store, repos, ledgers):
    texts = sentences(initiative)
    rows = store_rows(store)
    active, total = claims_by_task(ledgers)
    view, excluded = [], []
    for citation in sorted(texts):
        row = rows.get(citation)
        if is_provider(citation, row):
            excluded.append(citation)
            continue
        said = texts[citation]
        view.append({
            'citation': citation,
            'subject': row['subject'] if row else 'not_verified',
            'native_status': row['status'] if row else 'not_verified',
            'functional_role': declared(ROLE, said),
            'proposed_role': proposed_role(row) if row else 'not_verified',
            'verifier': declared(VERIFIER, said),
            # Una fila con ``owner`` nulo es un hecho medido (nadie asignado),
            # no una incognita: sin fila, si lo es.
            'operational_owner': (row['owner'] or 'unassigned') if row else 'not_verified',
            'session_identity': (row['session'] or 'not_verified') if row else 'not_verified',
            'execution_identity': 'not_verified',
            'resource_claims': f'{active[citation]}/{total[citation]}',
            'approval_authority': 'ejecutor (I-011)',
            'blocked_by': (row['blocked_by'] or '[]') if row else 'not_verified',
            'commits_naming': commits_naming(citation, repos),
        })
    return view, excluded


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--initiative', type=pathlib.Path, default=HOME / 'kaupamex-docs/source/gestion/pm/api/iniciativas/completar-raiz-orm')
    parser.add_argument('--store', type=pathlib.Path, default=THYROX / 'agent-results/agent_store.sqlite3')
    parser.add_argument('--out', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent / 'outputs' / 'responsibility_view.tsv')
    args = parser.parse_args(argv)
    repos = [HOME / 'kaupamex-api', HOME / 'kaupamex-docs']
    ledgers = [r / '.claude/coordination/claims.jsonl' for r in repos]
    view, excluded = build(args.initiative, args.store, repos, ledgers)
    args.out.parent.mkdir(exist_ok=True)
    columns = list(view[0]) if view else []
    with args.out.open('w', encoding='utf-8') as out:
        out.write('\t'.join(columns) + '\n')
        for row in view:
            out.write('\t'.join(str(row[c]) for c in columns) + '\n')
    by_role = collections.Counter()
    for row in view:
        for role in row['functional_role'].split(','):
            by_role[role] += 1
    print(f'universo: {len(view)} TASK del consumidor; {len(excluded)} del proveedor excluidas')
    print('| Responsabilidad funcional | TASK |')
    print('|---|---|')
    for role in (*ROLES, 'not_verified'):
        print(f'| {role} | {by_role[role]} |')
    proposed = collections.Counter(r['proposed_role'] for r in view)
    print('propuesta por asunto (inferida):', dict(proposed))
    status = collections.Counter(r['native_status'] for r in view)
    owners = collections.Counter(r['operational_owner'] for r in view)
    print('estado nativo:', dict(status))
    print('asignacion operativa:', dict(owners))
    print(f'salida: {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
