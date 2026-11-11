#!/bin/bash
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox DJANGO_SETTINGS_MODULE=config.settings.testing timeout 1500 uv run --frozen pytest -q --reuse-db -p no:randomly -W ignore -n 4 tests/integration/base tests/integration/company tests/unit/base tests/unit/orm tests/unit/utm 2>&1 | tail -25
