#!/usr/bin/env bash
# La suite completa dos veces: con la referencia y con ODOO_TOOLS apuntando a
# una ruta inexistente. Uso: run_with_and_without_reference.sh <directorio-salida>
set -u
OUT="${1:?directorio de salida}"
cd "$(dirname "$0")/../../.." || exit 9
unset ODOO19C ODOO18C ODOO19E ODOO18E
timeout 1500 uv run pytest -n 4 -q -p no:cacheprovider --reuse-db \
    --junitxml="$OUT/junit_with_reference.xml" </dev/null \
    > "$OUT/suite_with_reference.log" 2>&1
echo "with=$?" >> "$OUT/suite_with_reference.log"
ODOO_TOOLS=/nonexistent-odoo-tools timeout 1500 uv run pytest -n 4 -q \
    -p no:cacheprovider --reuse-db \
    --junitxml="$OUT/junit_without_reference.xml" </dev/null \
    > "$OUT/suite_without_reference.log" 2>&1
echo "without=$?" >> "$OUT/suite_without_reference.log"
