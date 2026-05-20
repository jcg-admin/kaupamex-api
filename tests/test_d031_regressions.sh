#!/bin/bash
# tests/test_d031_regressions.sh — D-031 regression tests
# Detecta regresion de los 6 fixes en bootstrap.sh + check_tools.sh
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXIT=0
fail() { echo "FAIL: $*" >&2; EXIT=1; }
pass() { echo "PASS: $*"; }

# H-12: mariadb-client (no mysql-client) en apt install
if grep -qE 'install_apt_packages.*mariadb-client|libmariadb-dev' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh usa mariadb-client + libmariadb-dev"
else
    fail "bootstrap.sh NO usa mariadb-client (H-12 regresion)"
fi
if grep -qE '\bmysql-client\b' "$PROJECT_ROOT/scripts/bootstrap.sh" | grep -v "^#"; then
    fail "bootstrap.sh todavia referencia mysql-client (H-12 regresion)"
else
    pass "bootstrap.sh no instala mysql-client"
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
if grep -qE 'import rest_framework\b|^.*rest_framework MySQLdb' "$PROJECT_ROOT/scripts/provisioners/system/check_tools.sh"; then
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

# H-17: mariadb (no mysql) como CLI canonico
if grep -qE 'command_exists mariadb' "$PROJECT_ROOT/scripts/provisioners/system/check_tools.sh"; then
    pass "check_tools.sh prefiere CLI mariadb (D-028)"
else
    fail "check_tools.sh sin deteccion de mariadb CLI (H-17 regresion)"
fi

echo ""
if [[ "$EXIT" -eq 0 ]]; then
    echo ">>> ALL PASS — D-031 fix integro"
else
    echo ">>> FAIL — D-031 regresion detectada"
fi
exit "$EXIT"

# H-19: pytest.ini con pythonpath + testpaths
if grep -qE '^pythonpath\s*=\s*practicayoruba' "$PROJECT_ROOT/pytest.ini"; then
    pass "pytest.ini define pythonpath = practicayoruba"
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

# H-22: db_qa_setup.sh pre-crea test_practicayoruba_qa
if grep -qE 'CREATE DATABASE IF NOT EXISTS.*test_' "$PROJECT_ROOT/scripts/provisioners/mysql/db_qa_setup.sh"; then
    pass "db_qa_setup.sh pre-crea test_<DB_NAME> (H-22 anti-hang)"
else
    fail "db_qa_setup.sh no pre-crea test_DB (H-22 regresion)"
fi

# H-23: bootstrap.sh propaga exit code de phase_database
if grep -qE 'BOOTSTRAP_FAILED|DB_PHASE_FAILED' "$PROJECT_ROOT/scripts/bootstrap.sh"; then
    pass "bootstrap.sh propaga estado de phase_database (H-23 loud failure)"
else
    fail "bootstrap.sh silenciaba fallos de phase_database (H-23 regresion)"
fi
