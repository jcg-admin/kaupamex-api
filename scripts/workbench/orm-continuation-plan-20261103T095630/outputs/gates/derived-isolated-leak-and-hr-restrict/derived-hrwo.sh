#!/bin/bash
# Derivado de HrWorkEntry.employee/version, HrUserWorkEntryEmployee.employee, MrpWorkorder.production -> PROTECT.
# Repetición tras el filtro de isolate_apps en _register (designs/isolated-apps-registry-leak.md).
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox DJANGO_SETTINGS_MODULE=config.settings.testing timeout 1700 uv run --frozen pytest -q --reuse-db -p no:randomly -W ignore -n 4 -rfE  tests/unit/hr tests/integration/hr tests/integration/sale tests/unit/orm tests/unit/resource 2>&1 | tail -40
