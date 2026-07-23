#!/bin/bash
# =============================================================================
# scripts/install-hooks.sh — activa los hooks de .githooks/ en este clone.
# =============================================================================
# Idempotente: ejecuta 'git config core.hooksPath .githooks' relativo a
# la raiz del submodulo api/.
#
# El hook pre-commit valida zero lazy imports en src/apps/**.
# Ver docs/source/gestion/pm/api/iniciativas/eliminar-lazy-imports-pep8/.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$REPO_ROOT/.githooks"

if [[ ! -d "$HOOKS_DIR" ]]; then
    echo "ERROR: $HOOKS_DIR no existe" >&2
    exit 1
fi

git config core.hooksPath .githooks
chmod +x "$HOOKS_DIR"/*

echo "OK: hooks activados (core.hooksPath = .githooks)"
echo "    Hooks instalados:"
for h in "$HOOKS_DIR"/*; do
    [[ -f "$h" ]] || continue
    echo "    - $(basename "$h")"
done
