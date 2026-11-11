#!/bin/bash
# Derivado de ResCompany.init (write): llamadores de init/init_models + compañía.
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox DJANGO_SETTINGS_MODULE=config.settings.testing timeout 1500 uv run --frozen pytest -q --reuse-db -p no:randomly -W ignore -n 4 tests/integration/base/test_load_modules.py tests/unit/base tests/unit/orm tests/unit/company tests/integration/company 2>&1 | tail -25
