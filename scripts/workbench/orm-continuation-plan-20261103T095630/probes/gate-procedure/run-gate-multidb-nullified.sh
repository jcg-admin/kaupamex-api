# Uso: run-gate-multidb-nullified.sh <revisión> <worktree>: el ci-multidb con
# el override de hr.employee.public escribiendo por la base por defecto.
set -u
R="$1"; W="$2"; GATE_SUFFIX="-null"
cd /home/user/thyrox || exit 2
THYROX_DISK_ADMISSION_FLOOR_MB=300 bash bin/resource_admission disk-admit --need-bytes $((380*1024*1024)) --owner $$ --path / --timeout 600 || { echo "ADMISSION-REFUSED"; echo EXIT=97; exit 97; }
cd /home/user/kaupamex-api || exit 2
git worktree add -q --detach "$W" "$R" || { echo EXIT=98; exit 98; }
cp src/.env "$W/src/.env"; cp .env "$W/.env" 2>/dev/null; ln -s /home/user/kaupamex-api/.venv "$W/.venv"
cd "$W" || exit 99
python3 - <<'PY' || { echo MUTATION-FAILED; echo EXIT=96; exit 96; }
import pathlib
p = pathlib.Path('addons/hr/models/hr_employee_public.py'); s = p.read_text()
o = 'connections[using or DEFAULT_DB_ALIAS].cursor()'
assert s.count(o) == 1
p.write_text(s.replace(o, 'connections[DEFAULT_DB_ALIAS].cursor()'))
PY
git diff --stat
BENCH=/home/user/kaupamex-api/scripts/workbench/orm-continuation-plan-20261103T095630/outputs/gates; THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex- uv run --frozen python scripts/run_multidb_isolation.py "$BENCH/ci-multidb-${R}${GATE_SUFFIX:-}"
rc=$?
cd /home/user/thyrox && bash bin/resource_admission disk-release --owner $$
echo EXIT=$rc
