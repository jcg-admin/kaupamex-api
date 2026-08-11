#!/bin/bash
# tests/test_bootstrap_first_run.sh
# Cubre bootstrap.sh + scripts/utils/provisioning.sh +
# scripts/provisioners/system/check_tools.sh + pytest.ini en la
# primera corrida sobre Ubuntu 24.04 noble fresh. Tambien verifica
# higiene del modelo cart.Cart (sin UniqueConstraint partial que
# dispara W036 en MariaDB).
#
# Hallazgos cerrados: H-12, H-13, H-14, H-15, H-16, H-18, H-19,
# H-21, H-22, H-23, H-24, H-25 (D-031) + H-26 (safe.directory) +
# H-27 (W036 cart.Cart) — ambos del followup post-D-032.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXIT=0
fail() { echo "FAIL: $*" >&2; EXIT=1; }
pass() { echo "PASS: $*"; }

# ADR-028: cliente PostgreSQL (libpq-dev + postgresql-client) en apt install
if grep -qE 'libpq-dev postgresql-client' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh instala libpq-dev + postgresql-client"
else
    fail "bootstrap.sh NO instala el cliente PostgreSQL (ADR-028)"
fi

# H-API-385: bootstrap NO debe reintroducir paquetes del motor retirado
if grep -qE 'mariadb-client|libmariadb-dev|mysql-client' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    fail "bootstrap.sh reintrodujo paquetes de MariaDB/MySQL (H-API-385 regresion)"
else
    pass "bootstrap.sh no instala paquetes del motor retirado"
fi
# H-API-385: el PYTHONPATH a practicayoruba/ murio con el rename a src/.
# kaupamex-bin resuelve el src-layout por si mismo.
if grep -qE 'PROJECT_ROOT\}/practicayoruba' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    fail "bootstrap.sh arma PYTHONPATH a practicayoruba/ (directorio inexistente)"
else
    pass "bootstrap.sh no usa el path muerto practicayoruba/"
fi

if grep -qE '"\$kbin"' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh invoca kaupamex-bin (punto de entrada del producto)"
else
    fail "bootstrap.sh no invoca kaupamex-bin"
fi

# H-13: .venv (no venv) como default
if grep -qE 'PROJECT_ROOT.*\.venv' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh usa .venv como default"
else
    fail "bootstrap.sh no usa .venv (H-13 regresion)"
fi

# H-14: _ensure_uv_installed existe
if grep -qE '^_ensure_uv_installed\(\)' "$PROJECT_ROOT/scripts/utils/provisioning.sh"; then
    pass "provisioning.sh define _ensure_uv_installed()"
else
    fail "provisioning.sh sin _ensure_uv_installed (H-14 regresion)"
fi
if grep -qE 'uv pip install' "$PROJECT_ROOT/scripts/utils/provisioning.sh"; then
    pass "setup_venv prefiere uv pip install"
else
    fail "setup_venv no usa uv (H-14 regresion)"
fi

# H-15: .env auto-create
if grep -qE 'cp.*env_example.*env_file|cp "\$env_example"' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh auto-crea .env desde .env.example"
else
    fail "bootstrap.sh no auto-crea .env (H-15 regresion)"
fi

# H-16: rest_framework (no djangorestframework) como modulo importable
if grep -qE 'import rest_framework\b|rest_framework psycopg' "$PROJECT_ROOT/scripts/provisioners/system/check_tools.sh"; then
    pass "check_tools.sh importa rest_framework (no djangorestframework)"
else
    fail "check_tools.sh aun importa djangorestframework (H-16 regresion)"
fi

# H-18: bootstrap.sh restaura ownership a SUDO_USER al final
if grep -qE "stat.*PROJECT_ROOT.*chown|chown.*repo_owner" "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh restaura ownership al owner del repo"
else
    fail "bootstrap.sh no chown al repo_owner post-sudo (H-18 regresion)"
fi

# ADR-028: psql como CLI canonico
if grep -qE 'command_exists psql' "$PROJECT_ROOT/scripts/provisioners/system/check_tools.sh"; then
    pass "check_tools.sh detecta el CLI psql"
else
    fail "check_tools.sh sin deteccion de psql (ADR-028)"
fi

# H-19: pytest.ini con pythonpath + testpaths
if grep -qE '^pythonpath\s*=\s*src' "$PROJECT_ROOT/pytest.ini"; then
    pass "pytest.ini define pythonpath = src"
else
    fail "pytest.ini sin pythonpath para que config sea importable (H-19 regresion)"
fi
if grep -qE '^testpaths\s*=\s*tests' "$PROJECT_ROOT/pytest.ini"; then
    pass "pytest.ini define testpaths = tests"
else
    fail "pytest.ini sin testpaths — pytest no encuentra los tests (H-19 regresion)"
fi

# H-21: pytest.ini con --reuse-db default
if grep -qE "^\s+--reuse-db" "$PROJECT_ROOT/pytest.ini"; then
    pass "pytest.ini incluye --reuse-db default (H-21)"
else
    fail "pytest.ini sin --reuse-db — pytest cuelga creando test DB (H-21 regresion)"
fi

# H-API-385: la base de QA la provisiona db, no api. bootstrap delega en el
# clon hermano en vez de duplicar el provisioner — la duplicacion fue el
# defecto que dejo dos copias divergentes del mismo script.
if grep -qE 'db_root.*provisioners/postgresql/db_setup.sh' "$PROJECT_ROOT/scripts/bootstrap.sh" \
   && grep -qE 'db_setup.sh" --qa' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh delega base y QA en db/provisioners/postgresql"
else
    fail "bootstrap.sh no delega el provisioning en db (H-API-385 regresion)"
fi

# H-23: bootstrap.sh propaga exit code de phase_database
if grep -qE 'BOOTSTRAP_FAILED|DB_PHASE_FAILED' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh propaga estado de phase_database (H-23 loud failure)"
else
    fail "bootstrap.sh silenciaba fallos de phase_database (H-23 regresion)"
fi

# H-24: scripts validan root al inicio
for f in scripts/bootstrap.sh; do
    if grep -qE 'id -u.*-ne 0|"\$\(id -u\)" -ne 0' "$PROJECT_ROOT/$f"; then
        pass "$(basename "$f") valida root al inicio (H-24)"
    else
        fail "$(basename "$f") no valida root (H-24 regresion — develop puede invocarlo)"
    fi
done

# ADR-028: tras instalar postgresql-client, pg_isready debe estar en PATH.
# Es el heredero de H-25: aquel re-resolvia MARIADB_CLI porque database.sh lo
# fijaba al sourcear, antes de que el paquete existiera. postgres_is_running
# resuelve pg_isready en cada llamada, asi que el problema no se reproduce —
# lo que se verifica es que bootstrap avise si el binario no quedo.
if grep -qE 'pg_isready no quedo en PATH' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh avisa si pg_isready no quedo tras instalar el cliente"
else
    fail "bootstrap.sh no verifica la presencia de pg_isready"
fi

# H-26: bootstrap registra git safe.directory para PROJECT_ROOT
# Evita "dubious ownership" cuando root toca repo de develop.
if grep -qE 'git config --global --add safe\.directory' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh registra git safe.directory (H-26)"
else
    fail "bootstrap.sh no registra git safe.directory (H-26 regresion — dubious ownership emergera)"
fi

# H-API-310 / H-API-385: el addon `cart` se retiro — su carrito vive en
# `sale`. Las dos afirmaciones H-27 median practicayoruba/apps/cart/models.py,
# un archivo que no existe desde el rename a src/ ni desde la retirada del
# addon; grep imprimia "No such file" y una de ellas pasaba por vacio.
if [[ -d "$PROJECT_ROOT/src/addons/cart" ]]; then
    fail "src/addons/cart reapareceio (el carrito vive en sale — H-API-310)"
else
    pass "addon cart retirado; el carrito vive en sale (H-API-310)"
fi

# H-LOG-1/2: bootstrap.sh detecta www-data y aplica chgrp+setgid en
# logs/ y media/ para que Apache pueda escribir.
if grep -qE 'getent group www-data' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh detecta www-data via getent group (H-LOG-1)"
else
    fail "bootstrap.sh no detecta www-data (H-LOG-1 regresion)"
fi
if grep -qE 'chgrp -R www-data' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh aplica chgrp www-data a runtime dirs (H-LOG-2)"
else
    fail "bootstrap.sh sin chgrp www-data (H-LOG-2 regresion)"
fi
# H-LOG-3: g+s (setgid) para que archivos nuevos hereden el grupo
if grep -qE 'chmod -R g\+w,g\+s' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh aplica g+w,g+s a runtime dirs (H-LOG-3 setgid propaga grupo)"
else
    fail "bootstrap.sh sin g+s (H-LOG-3 regresion — archivos nuevos no heredarian grupo)"
fi

# ----------------------------------------------------------------------------
# Iniciativa configurar-ui-dist-en-deploy (H-UID-1, H-UID-2)
# ----------------------------------------------------------------------------

# H-UID-1: .env.example documenta UI_DIST con path OVHCloud (produccion)
if grep -qE '^UI_DIST=/opt/practicayoruba/ui/dist' "$PROJECT_ROOT/src/.env.example"; then
    pass ".env.example documenta UI_DIST con path OVHCloud (H-UID-1)"
else
    fail ".env.example NO documenta UI_DIST OVHCloud (H-UID-1 regresion)"
fi

# H-UID-2: production.py default es '' (centinela), NO el path obsoleto /opt/...
if grep -qE "config\('UI_DIST', default=''\)" "$PROJECT_ROOT/src/config/settings/production.py"; then
    pass "production.py UI_DIST default='' (centinela, H-UID-2)"
else
    fail "production.py UI_DIST con default obsoleto (H-UID-2 regresion)"
fi
# El patron anterior era "default='/opt/practicayoruba" a secas: decia UI_DIST
# y medía CUALQUIER setting, así que enganchaba MEDIA_ROOT — otra variable, con
# una ruta de despliegue legítima. Se acota a la línea de UI_DIST.
if grep -qE "^UI_DIST = config\('UI_DIST', default='/opt/practicayoruba" \
        "$PROJECT_ROOT/src/config/settings/production.py"; then
    fail "UI_DIST todavia usa default /opt/practicayoruba (H-UID-2 regresion)"
else
    pass "UI_DIST sin default /opt/practicayoruba obsoleto (H-UID-2)"
fi

echo ""
if [[ "$EXIT" -eq 0 ]]; then
    echo ">>> ALL PASS — bootstrap first run integro"
else
    echo ">>> FAIL — regresion en bootstrap first run"
fi
exit "$EXIT"
