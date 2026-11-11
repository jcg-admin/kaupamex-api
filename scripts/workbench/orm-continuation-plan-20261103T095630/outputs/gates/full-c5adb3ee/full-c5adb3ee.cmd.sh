set -u
cd /home/user/thyrox && THYROX_DISK_ADMISSION_FLOOR_MB=300 bash bin/resource_admission disk-admit --need-bytes $((200*1024*1024)) --owner $$ --path / --timeout 600 || { echo ADMISSION-REFUSED; echo EXIT=97; exit 97; }
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex- DJANGO_SETTINGS_MODULE=config.settings.testing .venv/bin/python -m pytest -n 4 -q --reuse-db -p no:randomly -W ignore -rfE
rc=$?
cd /home/user/thyrox && bash bin/resource_admission disk-release --owner $$
echo EXIT=$rc
