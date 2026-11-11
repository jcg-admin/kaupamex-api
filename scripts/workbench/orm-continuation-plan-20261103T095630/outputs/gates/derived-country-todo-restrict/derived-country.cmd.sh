#!/bin/bash
# Derivado de ResCountryState.country, ResCity.country_id, IrActionsTodo.action -> PROTECT.
cd /home/user/kaupamex-api
THYROX_ROOT=/home/user/thyrox DJANGO_SETTINGS_MODULE=config.settings.testing timeout 1700 uv run --frozen pytest -q --reuse-db -p no:randomly -W ignore -n 4 -rfE tests/unit/base tests/integration/base tests/unit/orm tests/unit/hr tests/unit/base_vat tests/unit/base_address_extended tests/unit/account_edi_ubl_cii tests/unit/account tests/unit/service tests/unit/l10n_mx tests/unit/base_setup tests/unit/base_geolocalize tests/unit/fleet 2>&1 | tail -30
