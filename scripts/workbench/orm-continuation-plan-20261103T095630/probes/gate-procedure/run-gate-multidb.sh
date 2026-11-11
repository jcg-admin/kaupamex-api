# Uso: run-gate-multidb.sh <revisión> <directorio del worktree>
set -u
R="$1"; W="$2"
cd /home/user/thyrox || exit 2
THYROX_DISK_ADMISSION_FLOOR_MB=300 bash bin/resource_admission disk-admit --need-bytes $((380*1024*1024)) --owner $$ --path / --timeout 600 || { echo "ADMISSION-REFUSED"; echo EXIT=97; exit 97; }
echo "admitted owner=$$ rev=$R"
cd /home/user/kaupamex-api || exit 2
git worktree add -q --detach "$W" "$R" || { echo EXIT=98; exit 98; }
cp src/.env "$W/src/.env"; cp .env "$W/.env" 2>/dev/null; ln -s /home/user/kaupamex-api/.venv "$W/.venv"
cd "$W" || { echo EXIT=99; exit 99; }
BENCH=/home/user/kaupamex-api/scripts/workbench/orm-continuation-plan-20261103T095630/outputs/gates; THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex- uv run --frozen python scripts/run_multidb_isolation.py "$BENCH/ci-multidb-${R}${GATE_SUFFIX:-}"
rc=$?
cd /home/user/thyrox && bash bin/resource_admission disk-release --owner $$
echo EXIT=$rc
