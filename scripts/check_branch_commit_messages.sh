#!/bin/bash
# =============================================================================
# scripts/check_branch_commit_messages.sh
# Valida todos los commits del branch actual contra el hook commit-msg.
# =============================================================================
# El hook .githooks/commit-msg se ejecuta por commit, pero solo si
# install-hooks.sh fue corrido localmente. Si un contributor commitea
# sin el hook (clone nuevo sin install-hooks, --no-verify, ...), las
# violaciones se acumulan invisibles hasta la review.
#
# Este script corre el hook RETROACTIVAMENTE sobre todos los commits
# entre el HEAD actual y un base ref (default: develop). Util como
# gate pre-PR — el contributor lo corre antes de pedir review.
#
# Idempotente — solo lee git history. Reporta violaciones, NO modifica
# commits (la convencion prohibe reescribir history; ver I-002).
#
# Uso:
#   bash scripts/check_branch_commit_messages.sh              # base=develop
#   bash scripts/check_branch_commit_messages.sh main         # base=main
#   bash scripts/check_branch_commit_messages.sh feature/foo  # base=feature/foo
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOK="$PROJECT_ROOT/.githooks/commit-msg"
BASE="${1:-develop}"

[[ -x "$HOOK" ]] || {
    echo "FATAL: $HOOK no es ejecutable o no existe" >&2
    echo "       Corre: bash scripts/install-hooks.sh" >&2
    exit 2
}

if ! git -C "$PROJECT_ROOT" rev-parse --verify "$BASE" >/dev/null 2>&1; then
    echo "ERROR: ref base '$BASE' no existe" >&2
    echo "       Pasa una ref valida: bash $0 <base-ref>" >&2
    exit 2
fi

CURRENT="$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)"
COMMITS=$(git -C "$PROJECT_ROOT" rev-list "$BASE..HEAD" 2>/dev/null || echo "")

if [[ -z "$COMMITS" ]]; then
    echo "OK: rama '$CURRENT' no tiene commits ahead de '$BASE' — nada que validar"
    exit 0
fi

TOTAL=0
FAIL=0
TMP="$(mktemp -t check-branch.XXXX)"
trap 'rm -f "$TMP"' EXIT

echo "Validando commits de '$CURRENT' ahead de '$BASE'..."
echo ""

ERR_LOG="$(mktemp -t check-branch-err.XXXX)"
trap 'rm -f "$TMP" "$ERR_LOG"' EXIT

# Desactivar -e en el loop — los failures del hook son esperados y
# se manejan explicitamente con if/then.
set +e
for SHA in $COMMITS; do
    TOTAL=$((TOTAL + 1))
    SUBJECT="$(git -C "$PROJECT_ROOT" log -1 --pretty=format:"%s" "$SHA")"
    printf '%s\n' "$SUBJECT" > "$TMP"
    "$HOOK" "$TMP" > "$ERR_LOG" 2>&1
    if [[ "$?" -ne 0 ]]; then
        # Extraer razon (primera linea "ERROR commit-msg:" del log).
        REASON=$(grep -m1 -E "^ERROR commit-msg:" "$ERR_LOG" \
                 | sed 's/^ERROR commit-msg: //')
        [[ -z "$REASON" ]] && REASON="(hook fallo sin razon especificada)"
        printf "  FAIL %s  %s\n" "${SHA:0:7}" "$SUBJECT"
        printf "       motivo: %s\n" "$REASON"
        FAIL=$((FAIL + 1))
    fi
done
set -e

echo ""
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL PASS — $TOTAL/$TOTAL commits respetan Tim Pope (vs $BASE)"
    exit 0
else
    echo "FAIL — $FAIL/$TOTAL commits violan Tim Pope (vs $BASE)"
    echo ""
    echo "El historial NO se reescribe (I-002 + commit-conventions.md)."
    echo "Lo que SI se hace:"
    echo "  - Asegurarse que install-hooks.sh esta corrido antes del proximo commit"
    echo "  - Si el branch aun no se ha mergeado y son commits propios, considerar"
    echo "    un squash-rebase ANTES del PR (no despues)"
    echo "  - En review, llamar la atencion del autor para futuras instancias"
    exit 1
fi
