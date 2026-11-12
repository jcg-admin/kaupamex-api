# Uso: run-gate-multidb-staged.sh <revisión> <directorio del worktree> <directorio de trabajo>
# Escribe la salida en curso en <directorio de trabajo> (fuera del banco): el
# banco sólo recibe evidencia finalizada, con persist_gate_evidence.py.
# MULTIDB_SECOND_BASE=clone|provision se propaga al fixture.
set -u
R="$1"; W="$2"; OUT="$3"
cd /home/user/thyrox || exit 2
THYROX_DISK_ADMISSION_FLOOR_MB=300 bash bin/resource_admission disk-admit --need-bytes $((380*1024*1024)) --owner $$ --path / --timeout 600 || { echo "ADMISSION-REFUSED"; echo EXIT=97; exit 97; }
echo "admitted owner=$$ rev=$R second_base=${MULTIDB_SECOND_BASE:-provision} at=$(date -u +%FT%T)"
cd /home/user/kaupamex-api || exit 2
git worktree add -q --detach "$W" "$R" || { echo EXIT=98; exit 98; }
cp src/.env "$W/src/.env"; cp .env "$W/.env" 2>/dev/null; ln -s /home/user/kaupamex-api/.venv "$W/.venv"
cd "$W" || { echo EXIT=99; exit 99; }
THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex- uv run --frozen python scripts/run_multidb_isolation.py "$OUT"
rc=$?
echo "finished at=$(date -u +%FT%T)"
cd /home/user/thyrox && bash bin/resource_admission disk-release --owner $$
echo EXIT=$rc
