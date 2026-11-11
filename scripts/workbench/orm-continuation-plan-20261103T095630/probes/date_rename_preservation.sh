#!/bin/bash
# Antes/después del renombre de las fechas del log-access (hija B de
# TASK-API-0485, designs/log-access-date-names.md).
#
# Uso: date_rename_preservation.sh <worktree-C> <worktree-B> <base> <salida>
#
# 1. Migra <base> (desechable, se crea aquí) al estado del worktree C.
# 2. Toma una muestra: id y las dos fechas de tablas con filas sembradas, más
#    el conteo de filas de cada una.
# 3. Migra la misma base con el worktree B (RENAME COLUMN).
# 4. Lee la misma muestra con los nombres nuevos y compara fila a fila.
#
# Sale 0 si todas las filas conservan sus dos fechas y el conteo; 1 si no.
# No borra la base: la deja para inspección; su retirada es un paso aparte.
set -euo pipefail
WT_C=$1; WT_B=$2; DB=$3; OUT=$4
PY=/home/user/kaupamex-api/.venv/bin/python
TABLES=(res_country res_currency res_lang res_partner ir_model_data ir_module_module)
mkdir -p "$OUT"
psql_db() { sudo -u postgres psql -d "$DB" -tA -F $'\t' -c "$1"; }

sudo -u postgres createdb -O orm_x2hokp "$DB"
(cd "$WT_C" && DB_NAME="$DB" DJANGO_SETTINGS_MODULE=config.settings.development \
    "$PY" src/manage.py migrate --no-input > "$OUT/migrate-C.log" 2>&1)

: > "$OUT/before.tsv"
for t in "${TABLES[@]}"; do
    psql_db "SELECT '$t', count(*) FROM $t" >> "$OUT/counts-before.tsv"
    psql_db "SELECT '$t', id, created_at, updated_at FROM $t ORDER BY id" \
        >> "$OUT/before.tsv"
done

(cd "$WT_B" && DB_NAME="$DB" DJANGO_SETTINGS_MODULE=config.settings.development \
    "$PY" src/manage.py migrate --no-input > "$OUT/migrate-B.log" 2>&1)

: > "$OUT/after.tsv"
for t in "${TABLES[@]}"; do
    psql_db "SELECT '$t', count(*) FROM $t" >> "$OUT/counts-after.tsv"
    psql_db "SELECT '$t', id, create_date, write_date FROM $t ORDER BY id" \
        >> "$OUT/after.tsv"
done
psql_db "SELECT count(*) FROM information_schema.columns
         WHERE column_name IN ('created_at','updated_at')
           AND table_schema = 'public'" > "$OUT/old-columns-left.txt"

rows=$(wc -l < "$OUT/before.tsv")
if cmp -s "$OUT/before.tsv" "$OUT/after.tsv" \
        && cmp -s "$OUT/counts-before.tsv" "$OUT/counts-after.tsv"; then
    echo "PRESERVADAS: $rows filas, conteos iguales; columnas viejas: $(cat "$OUT/old-columns-left.txt")"
    exit 0
fi
echo "DIFERENCIAS: ver before.tsv/after.tsv en $OUT"
exit 1
