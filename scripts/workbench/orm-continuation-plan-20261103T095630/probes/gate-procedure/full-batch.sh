set -u
cd /home/user/thyrox && THYROX_DISK_ADMISSION_FLOOR_MB=300 bash bin/resource_admission disk-admit --need-bytes $((200*1024*1024)) --owner $$ --path / --timeout 600 || { echo ADMISSION-REFUSED; echo EXIT=97; exit 97; }
cd /home/user/kaupamex-api
bash scripts/workbench/orm-continuation-plan-20261103T095630/probes/gate-procedure/ensure-postgres.sh || { echo EXIT=96; exit 96; }
# Preflight (intervención 4.3.1 §3.5): sin bases sanas no se lanza la suite.
DJANGO_SETTINGS_MODULE=config.settings.testing .venv/bin/python scripts/gate_preflight.py --prepare --workers 4 || { cd /home/user/thyrox && bash bin/resource_admission disk-release --owner $$; echo PREFLIGHT-REFUSED; echo EXIT=95; exit 95; }
# Stop-on-error (§3.2): --maxfail=1 detiene xdist tras el primer fallo
# (medido: 14 de 40 casos, rc=2). test_multidb_isolation se excluye porque
# sus 15 errores son de diseño en F2 y su veredicto lo da F3
# (scripts/run_multidb_isolation.py); dejarlos dentro haría saltar el corte.
THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex- DJANGO_SETTINGS_MODULE=config.settings.testing .venv/bin/python -m pytest -n 4 -q --reuse-db -p no:randomly -W ignore -rfE --maxfail=1 --ignore=tests/integration/company/test_multidb_isolation.py
rc=$?
cd /home/user/thyrox && bash bin/resource_admission disk-release --owner $$
echo EXIT=$rc
