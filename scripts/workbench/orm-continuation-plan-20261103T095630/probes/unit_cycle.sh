#!/usr/bin/env bash
# Ciclo de una unidad diferencial del plan: claim, commit de la prueba, fila
# del plan, asiento, evidencia, inventario, publicación y SELECCIÓN DE LA
# SIGUIENTE. Uso:
#   unit_cycle.sh <prueba> <modulo> <id> <TASK> <mensaje-de-la-prueba> [excluidos]
# excluidos: símbolos separados por comas que NO reciben evidencia.
# CYCLE_INCLUDE=<archivo modulo<TAB>simbolo> restringe la unidad a esos
# símbolos; ausente o vacío, el ciclo rehúsa (exit 8), igual que una unidad
# sin obligaciones. CYCLE_CANDIDATES=<filas JSON Lines> abastece la frontera
# con local_plan supply si queda agotada. CYCLE_NODE fija el nodo.
#
# Los temporales van a un directorio de mktemp: el ciclo no depende de la
# ruta de una sesión.
set -u
S="$(mktemp -d)"
test -n "$S" || exit 9
trap 'rm -rf "${S:?}"' EXIT
F=$1 M=$2 ID=$3 TASK=$4 MSG=$5 EXCLUDE=${6:-}
NODE="${CYCLE_NODE:-x2hokp}"
THYROX="${THYROX_ROOT:-/home/user/thyrox}"
if [ -n "${CYCLE_INCLUDE:-}" ] && [ ! -s "$CYCLE_INCLUDE" ]; then
  echo "CYCLE_INCLUDE missing or empty: $CYCLE_INCLUDE"; exit 8
fi
API="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"; cd "$API" || exit 9
W=scripts/workbench/orm-continuation-plan-20261103T095630
C=scripts/workbench/orm-symbol-presence-census-20260910T175850
ADM=scripts/evidence/ci-local-fail-fast-20261022T004947/outputs/pre-commit-admission.json
commit() {  # mensaje, rutas...
  local msg=$1; shift
  PATH="$PWD/.venv/bin:$PATH" GIT_AUTHOR_NAME="Nestor Monroy" \
    GIT_AUTHOR_EMAIL="46802445+NestorMonroy@users.noreply.github.com" \
    git commit -q -F "$msg" -- "$@" </dev/null > "$S/precommit.out" 2>&1
  local rc=$?
  git checkout -- "$ADM" 2>/dev/null
  if [ $rc -ne 0 ]; then echo "COMMIT FAILED ($rc)"; tail -15 "$S/precommit.out"; exit 4; fi
  echo "commit $(git log -1 --format=%h)"
}
# 1. claims: soltar los propios, reclamar la prueba
(cd "$THYROX" && PYTHONPATH=src API="$API" NODE="$NODE" python3 - "$F" "$TASK" <<'PY'
import json, os, sys, uuid, datetime
from session import claim_fold as c
path, task = sys.argv[1], sys.argv[2]
L = os.environ['API'] + '/.claude/coordination/claims.jsonl'
node = 'VM-' + os.environ['NODE']  # dueño del ledger; Thyrox compara vm-<nodo> en minúsculas
n = datetime.datetime.now(datetime.timezone.utc)
at = n.strftime('%Y-%m-%dT%H:%M:%S.') + '%03dZ' % (n.microsecond // 1000)
rows = [json.loads(l) for l in open(L) if l.strip()]
active = c.active_claims(rows)
foreign = [k for k in active if k['owner'] != node]
if any(k['path'] == path for k in foreign):
    sys.exit(f'claim ajeno sobre {path}: {foreign}')
out = [dict(id='c-' + str(uuid.uuid4()), op='release', path=k['path'], owner=k['owner'],
            branch=k['branch'], at=at, task=k['task']) for k in active if k['owner'] == node]
out.append(dict(id='c-' + str(uuid.uuid4()), op='claim', path=path, owner=node,
                branch='claude/bold-fermat-x2hokp', at=at, task=task))
open(L, 'a').writelines(json.dumps(o, separators=(',', ':')) + '\n' for o in out)
print('claimed', path)
PY
) || exit 5
git add -N "$F"
if git diff --quiet HEAD -- "$F"; then
  printf 'Claim a committed test for its plan cycle

The test is already committed; this claim covers its cycle:
%s

Refs: %s
' "$F" "$TASK" > "$S/cycle_claim_msg.txt"
  commit "$S/cycle_claim_msg.txt" .claude/coordination/claims.jsonl
else
  commit "$MSG" "$F" .claude/coordination/claims.jsonl
fi
TEST_COMMIT=$(git log -1 --format=%h)
# 2. fila del plan
awk -F'\t' -v m="$M" '$2==m && $5=="not_verified" && $4!="file"{print $3"\t"$4}' \
  $C/outputs/inventory_by_kind.tsv \
  | awk -F'\t' -v ex=",$EXCLUDE," 'index(ex, ","$1",")==0' > "$S/cycle_syms.tsv"
if [ -n "${CYCLE_INCLUDE:-}" ]; then
  awk -F'	' 'NR==FNR{keep[$2]=1;next} ($1 in keep)' "$CYCLE_INCLUDE" "$S/cycle_syms.tsv" > "$S/cycle_syms.kept"
  mv "$S/cycle_syms.kept" "$S/cycle_syms.tsv"; echo "included from $CYCLE_INCLUDE"
fi
[ -n "$EXCLUDE" ] && echo "excluded: $EXCLUDE"
N=$(wc -l < "$S/cycle_syms.tsv"); echo "obligations $N"
if [ "$N" -eq 0 ]; then echo "NO OBLIGATIONS: refusing an empty unit"; exit 8; fi
python3 - "$S/cycle_syms.tsv" "$S/cycle_row.jsonl" "$ID" "$TASK" "$F" "$M" <<'PY'
import json, sys
syms_path, out, rid, task, test, module = sys.argv[1:]
syms = [l.split('\t')[0] for l in open(syms_path).read().splitlines()]
name = module.rsplit('/', 1)[1]
row = dict(id=rid, taskId=task, candidates=['claude-opus-5-5'], owned=[test], dependsOn=[],
           obligations=[f'{module}::{s}' for s in syms],
           verify=f'uv run pytest -q -p no:cacheprovider {test}',
           prompt=f'Verificar {name} contra odoo19c ejecutada; prueba en {test}.')
open(out, 'w').write(json.dumps(row, ensure_ascii=False) + '\n')
PY
(cd "$THYROX" && PYTHONPATH=src timeout 120 uv run --quiet python -m session.local_plan \
  incorporate "$API/$W" --rows "$S/cycle_row.jsonl" --planner plan_coverage --target "$API" </dev/null 2>&1 | tail -1)
printf 'Incorporate a unit into the plan\n\nThe row %s ties %s pending obligations of %s to the\ndifferential test committed in %s.\n\nRefs: %s\n' \
  "$ID" "$N" "$M" "$TEST_COMMIT" "$TASK" > "$S/cycle_msg.txt"
commit "$S/cycle_msg.txt" $W/plan.jsonl $W/plan.provenance.json
# 3. asiento
THYROX_ROOT="$THYROX" timeout 300 .venv/bin/python $W/probes/settle_item.py $W "$ID" </dev/null 2>&1 | tail -2 | cut -c1-200
if ! python3 -c "import json,sys; sys.exit(0 if any(json.loads(l).get('kind')=='accepted' and json.loads(l).get('item')==sys.argv[1] for l in open(sys.argv[2]) if l.strip()) else 1)" "$ID" "$W/outputs/continuation.jsonl"; then
  echo "NOT SETTLED: $ID has no accepted record; stopping before evidence"; exit 7
fi
SETTLE=$(git log -1 --format=%h)
# 4. evidencia e inventario
awk -F'\t' -v t="$F" -v m="$M" '{print m"\t"$1"\t"$2"\t"t}' "$S/cycle_syms.tsv" >> $C/outputs/verified_contracts.tsv
timeout 300 env PYTHONPATH=scripts .venv/bin/python $C/inventory_by_kind.py </dev/null 2>&1 \
  | grep -E '^\| (Archivos|Clases|Funciones|Metodos|Atributos|Propiedades)'
echo "module rows:"; grep "	$M	" $C/outputs/inventory_by_kind.tsv | cut -f5 | sort | uniq -c
printf 'Record a settled unit in plan and inventory\n\nsettle_item closed %s at %s, and %s evidence rows\npoint at the differential test.\n\nRefs: %s\n' \
  "$ID" "$SETTLE" "$N" "$TASK" > "$S/cycle_msg.txt"
commit "$S/cycle_msg.txt" $W/outputs $C/outputs
# 5. publicación
git push -q -u origin claude/bold-fermat-x2hokp 2>&1 | tail -2
git fetch -q origin claude/bold-fermat-x2hokp
if [ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ]; then echo "published $(git log -1 --format=%h)"; else echo "NOT PUBLISHED"; exit 6; fi
git status --short
# 6. siguiente unidad: la selección es del Provider, no de este script
LEDGER="$API/.claude/coordination/claims.jsonl"
NEXT=$(cd "$THYROX" && PYTHONPATH=src python3 -m session.task_continuation next "$API/$W" \
  --node "$NODE" --claims-ledger "$LEDGER" 2>&1 | tail -1)
echo "next: $NEXT"
if [ "${NEXT#nada despachable}" != "$NEXT" ] && [ -n "${CYCLE_CANDIDATES:-}" ]; then
  (cd "$THYROX" && PYTHONPATH=src python3 -m session.local_plan supply "$API/$W" \
    --candidates "$CYCLE_CANDIDATES" --node "$NODE" --claims-ledger "$LEDGER" \
    --planner unit_cycle --target "$API" 2>&1 | tail -1)
fi
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('coverage:', d['verdict'], 'frontera', len(d['frontier']), 'sin unidad', len(d['unrepresented']))" "$API/$W/outputs/plan_coverage.json"
