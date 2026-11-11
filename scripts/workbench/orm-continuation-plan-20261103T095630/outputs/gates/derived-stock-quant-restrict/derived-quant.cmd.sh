#!/bin/bash
# Derivado de StockQuant.product/location/lot -> PROTECT (consumidores de quants, productos, ubicaciones y lotes).
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox DJANGO_SETTINGS_MODULE=config.settings.testing timeout 1700 uv run --frozen pytest -q --reuse-db -p no:randomly -W ignore -n 4 -rfE  tests/unit/stock tests/integration/stock tests/integration/sale tests/unit/product tests/integration/product tests/unit/purchase_stock tests/unit/orm tests/unit/tools 2>&1 | tail -30
