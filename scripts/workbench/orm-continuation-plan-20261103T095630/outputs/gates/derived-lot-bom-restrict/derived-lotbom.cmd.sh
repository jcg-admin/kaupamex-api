#!/bin/bash
# Derivado de StockLot.product y MrpBom.product_tmpl -> PROTECT.
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox DJANGO_SETTINGS_MODULE=config.settings.testing timeout 1700 uv run --frozen pytest -q --reuse-db -p no:randomly -W ignore -n 4 -rfE  tests/unit/stock tests/integration/sale tests/unit/product tests/integration/product tests/unit/orm tests/unit/purchase_stock 2>&1 | tail -40
