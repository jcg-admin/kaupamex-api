#!/usr/bin/env bash
# Experimento de continuidad con los mecanismos reales: selección
# (task_continuation next), abastecimiento (local_plan supply) y asiento por la
# vía del Consumer (settle_item.py). Escribe sólo en outputs/ del banco.
# Uso: bash run_experiment.sh  (con el árbol limpio; THYROX_ROOT opcional)
set -u
BENCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API="$(cd "$BENCH/../../.." && pwd)"
THYROX="${THYROX_ROOT:-/home/user/thyrox}"
SETTLE="$API/scripts/workbench/orm-continuation-plan-20261103T095630/probes/settle_item.py"
LOG="$BENCH/outputs/experiment.log"
: > "$BENCH/outputs/continuation.jsonl"
: > "$LOG"
step() { echo "== $*" | tee -a "$LOG"; }
frontier() {
  (cd "$THYROX" && PYTHONPATH=src python3 -m session.task_continuation next "$BENCH" 2>&1) | tee -a "$LOG"
}
node_frontier() {
  (cd "$THYROX" && PYTHONPATH=src python3 -m session.task_continuation next "$BENCH" \
    --node VM-x2hokp --claims-ledger "$BENCH/claims-fixture.jsonl" 2>&1) | tee -a "$LOG"
}
settle() {
  THYROX_ROOT="$THYROX" python3 "$SETTLE" "$BENCH" "$1" > "$BENCH/outputs/settle-$1.out" 2>&1
  echo "settle $1 exit=$?: $(grep -v '^coverage' "$BENCH/outputs/settle-$1.out" | tail -1)" | tee -a "$LOG"
}
doomed() {
  (cd "$THYROX" && PYTHONPATH=src python3 -c "
import sys
from pathlib import Path
from session.task_continuation import load_plan, read_log, exposed_credentials
from session.continuation_frontier import item_states, doomed_items
b = Path(sys.argv[1])
for entry, reason in doomed_items(load_plan(b), item_states(read_log(b)), exposed_credentials(b)):
    print(entry.id, '->', reason)
" "$BENCH") | tee -a "$LOG"
}
step "1. frontera inicial"; frontier
step "2. frontera del nodo"; node_frontier
step "3. ítems que no pueden correr en esta ejecución"; doomed
step "4. asiento de A (vía Consumer)"; settle A
step "5. frontera tras A: B, C (dependía de A) y E"; frontier
step "6. A no vuelve a la frontera"; frontier | grep -qw A && echo "A REPETIDA" | tee -a "$LOG" || echo "A no se repite" | tee -a "$LOG"
step "7. asiento de E, sin obligaciones"; settle E
step "8. asiento de B y C"; settle B; settle C
step "9. frontera agotada"; frontier
step "10. abastecimiento: F sin prueba roja, G con prueba existente"
(cd "$THYROX" && PYTHONPATH=src python3 -m session.local_plan supply "$BENCH" \
  --candidates "$BENCH/candidates.jsonl" --node VM-x2hokp \
  --claims-ledger "$BENCH/claims-fixture.jsonl" --planner continuity-experiment \
  --target "$API" 2>&1) | tee -a "$LOG"
step "11. frontera tras abastecer"; frontier
