#!/bin/bash
# =============================================================================
# scripts/test_commit_msg_hook.sh
# Regression test del hook .githooks/commit-msg.
# =============================================================================
# Valida que el hook acepta mensajes Tim Pope validos y rechaza los
# que violan las 4 reglas mecanicas (largo, mayuscula, no punto,
# imperativo). Tambien valida que respeta las excepciones (Merge,
# Revert, fixup!, squash!, amend!).
#
# Idempotente — solo crea archivos en /tmp/ y los borra al final.
#
# Uso:
#   bash scripts/test_commit_msg_hook.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOK="$PROJECT_ROOT/.githooks/commit-msg"

[[ -x "$HOOK" ]] || { echo "FATAL: $HOOK no existe o no es ejecutable" >&2; exit 1; }

TMPDIR="$(mktemp -d -t commit-msg-test.XXXX)"
trap 'rm -rf "$TMPDIR"' EXIT

EXIT=0
PASS=0
FAIL_COUNT=0

# expect_pass <msg> <description>
expect_pass() {
    local msg="$1" desc="$2"
    local f="$TMPDIR/msg_$$.txt"
    echo "$msg" > "$f"
    if "$HOOK" "$f" >/dev/null 2>&1; then
        echo "PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "FAIL: $desc — el hook rechazo un mensaje valido" >&2
        echo "       Mensaje: '$msg'" >&2
        EXIT=1
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# expect_fail <msg> <description>
expect_fail() {
    local msg="$1" desc="$2"
    local f="$TMPDIR/msg_$$.txt"
    echo "$msg" > "$f"
    if "$HOOK" "$f" >/dev/null 2>&1; then
        echo "FAIL: $desc — el hook acepto un mensaje invalido" >&2
        echo "       Mensaje: '$msg'" >&2
        EXIT=1
        FAIL_COUNT=$((FAIL_COUNT + 1))
    else
        echo "PASS: $desc"
        PASS=$((PASS + 1))
    fi
}

# ----------------------------------------------------------------------------
# Casos validos
# ----------------------------------------------------------------------------
expect_pass "Add new feature" \
    "imperativo simple aceptado"
expect_pass "Fix race condition in cart save" \
    "imperativo con multiples palabras aceptado"
expect_pass "Remove deprecated MySQL CLI references" \
    "imperativo con 'deprecated' en posicion no-primera aceptado"
expect_pass "Refactor login flow to use JWT cookies" \
    "subject largo pero <72 ch aceptado"
expect_pass "Document WSL2 user model in db scripts" \
    "imperativo Document con sustantivo 'model' aceptado"

# ----------------------------------------------------------------------------
# Excepciones (autogenerados por git)
# ----------------------------------------------------------------------------
expect_pass "Merge pull request #42 from feature/foo" \
    "Merge commit auto-aceptado"
expect_pass "Revert \"Add buggy feature\"" \
    "Revert commit auto-aceptado"
expect_pass "fixup! Add new feature" \
    "fixup! auto-aceptado"
expect_pass "squash! Add new feature" \
    "squash! auto-aceptado"
expect_pass "amend! Add new feature" \
    "amend! auto-aceptado"

# ----------------------------------------------------------------------------
# Violaciones — debe rechazar
# ----------------------------------------------------------------------------
expect_fail "add new feature" \
    "rechaza subject en minuscula"
expect_fail "Add new feature." \
    "rechaza subject con punto final"
expect_fail "Added new feature" \
    "rechaza primer verbo en pasado (-ed)"
expect_fail "Adding new feature" \
    "rechaza primer verbo en gerundio (-ing)"
expect_fail "$(printf 'Add %.0s' {1..30})feature" \
    "rechaza subject de mas de 72 caracteres"

# ----------------------------------------------------------------------------
# Cierre
# ----------------------------------------------------------------------------
echo ""
TOTAL=$((PASS + FAIL_COUNT))
if [[ "$EXIT" -eq 0 ]]; then
    echo ">>> ALL PASS — $PASS/$TOTAL checks. commit-msg hook integro."
else
    echo ">>> FAIL — $FAIL_COUNT/$TOTAL checks fallaron en commit-msg hook."
fi
exit "$EXIT"
