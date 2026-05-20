#!/bin/bash
# tests/test_d031_part2.sh — D-031 part 2: api db provisioners CLI rename
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXIT=0
fail() { echo "FAIL: $*" >&2; EXIT=1; }
pass() { echo "PASS: $*"; }

# utils/database.sh debe tener los helpers
for fn in mariadb_client_bin mariadb_admin_bin; do
    if grep -qE "^${fn}\(\)" "$PROJECT_ROOT/scripts/utils/database.sh"; then
        pass "utils/database.sh define ${fn}()"
    else
        fail "utils/database.sh NO define ${fn}() (D-031 part2 regresion)"
    fi
done

# Variables exportadas al sourcear
for var in MARIADB_CLI MARIADB_ADM; do
    if grep -qE "^${var}=" "$PROJECT_ROOT/scripts/utils/database.sh"; then
        pass "utils/database.sh asigna ${var} al cargar"
    else
        fail "utils/database.sh no asigna ${var} (regresion)"
    fi
done

# Provisioners NO contienen bare mysql/mysqladmin como binario
for f in scripts/provisioners/mysql/db_setup.sh \
         scripts/provisioners/mysql/db_qa_setup.sh \
         scripts/utils/database.sh; do
    leaks=$(grep -nE "(^|[[:space:]])(mysql|mysqladmin)[[:space:]]+(--socket|-h \"\\\$DB|--batch|ping --silent|--user|-e )" "$PROJECT_ROOT/$f" \
            | grep -vE 'mariadb-admin|MariaDB|mariadb-client|legacy|service mysql|mysql:|^#|mysql\.' || true)
    if [[ -z "$leaks" ]]; then
        pass "$(basename "$f") usa MARIADB_CLI/MARIADB_ADM (sin bare mysql)"
    else
        fail "$(basename "$f") tiene llamadas bare a mysql/mysqladmin:"
        echo "$leaks" | sed 's/^/        /' >&2
    fi
done

# check_prerequisites valida MARIADB_CLI (no command -v mysql)
for f in scripts/provisioners/mysql/db_setup.sh scripts/provisioners/mysql/db_qa_setup.sh; do
    if grep -qE 'MARIADB_CLI.*\|\|.*log_fatal' "$PROJECT_ROOT/$f"; then
        pass "$(basename "$f") check_prerequisites usa MARIADB_CLI"
    else
        fail "$(basename "$f") usa command -v mysql legacy (regresion)"
    fi
done

echo ""
if [[ "$EXIT" -eq 0 ]]; then
    echo ">>> ALL PASS — D-031 part 2 fix integro"
else
    echo ">>> FAIL — D-031 part 2 regresion detectada"
fi
exit "$EXIT"
