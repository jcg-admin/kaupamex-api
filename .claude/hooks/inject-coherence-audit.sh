#!/usr/bin/env bash
# SessionStart hook — corre la auditoría mecánica de coherencia (modo --fast,
# sin el gate lento de referencias) e inyecta el SCORE al inicio de cada
# sesión. Así el tool /thyrox:audit-coherence se USA siempre (no queda como
# capacidad muerta), surfacing no-bloqueante de la coherencia del repo.
# Nunca rompe el flujo: sale 0 siempre.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT="$ROOT/.claude/scripts/thyrox-audit.sh"

MSG="THYROX coherencia: script no encontrado."
if [[ -f "$SCRIPT" ]]; then
    OUT="$(bash "$SCRIPT" --fast 2>/dev/null || true)"
    SCORE="$(printf '%s\n' "$OUT" | sed -n 's/^## Score: //p' | head -1)"
    FAILED="$(printf '%s\n' "$OUT" | grep -E '^FAIL' | sed 's/^FAIL *. */ - /' | tr '\n' ';' | cut -c1-300)"
    if [[ -z "$SCORE" ]]; then SCORE="no calculado"; fi
    MSG="THYROX coherencia del repo (gate automatico, --fast): ${SCORE}. Corre /thyrox:audit-coherence para el reporte completo + triage. FAILs: ${FAILED:-ninguno}. (WARN 'candidatos a deriva' = triage cualitativo, no bug automatico.)"
fi

# Emitir JSON con escape seguro del mensaje (python json.dumps).
python3 - "$MSG" <<'PY' 2>/dev/null || { echo '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"THYROX coherencia: hook con error (no bloqueante)."}}'; exit 0; }
import json, sys
msg = sys.argv[1]
print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": msg}}))
PY
exit 0
