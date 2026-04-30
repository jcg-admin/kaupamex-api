#!/bin/bash
# =============================================================================
# check_tools.sh — Verifica el estado del entorno — PracticaYoruba API
# =============================================================================
# Uso:
#   bash scripts/provisioners/system/check_tools.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${PROJECT_ROOT}/scripts/utils/logging.sh"
source "${PROJECT_ROOT}/scripts/utils/core.sh"
source "${PROJECT_ROOT}/scripts/utils/network.sh"

# Activar venv si existe
VENV_PYTHON="${PROJECT_ROOT}/venv/bin/python3"
if exists_file "$VENV_PYTHON"; then
    export PATH="${PROJECT_ROOT}/venv/bin:${PATH}"
fi

# Leer .env
ENV_FILE="${PROJECT_ROOT}/practicayoruba/.env"
if exists_file "$ENV_FILE"; then
    set -a; source "$ENV_FILE"; set +a
fi

POSTGRES_HOST="${DB_HOST:-127.0.0.1}"
POSTGRES_PORT="${DB_PORT:-5432}"

ERRORS=0; WARNINGS=0; OK=0

ok()   { log_success "$1"; OK=$(( OK + 1 )); }
warn() { log_warn "$1";    WARNINGS=$(( WARNINGS + 1 )); }
fail() { log_error "$1";   ERRORS=$(( ERRORS + 1 )); }

# =============================================================================
check_system() {
    log_header "Sistema"

    command_exists python3 \
        && ok "python3: $(python3 --version 2>&1)" \
        || fail "python3 no encontrado"

    command_exists psql \
        && ok "psql: $(psql --version 2>&1 | head -1)" \
        || warn "psql no encontrado (instala postgresql-client)"
}

# =============================================================================
check_venv() {
    log_header "Entorno virtual"

    if exists_dir "${PROJECT_ROOT}/venv"; then
        ok "venv existe: ${PROJECT_ROOT}/venv"
    else
        warn "venv no existe — ejecuta: python3 -m venv venv"
        return
    fi

    for pkg in django djangorestframework psycopg2 rest_framework_simplejwt; do
        "${PROJECT_ROOT}/venv/bin/python3" -c "import ${pkg//-/_}" 2>/dev/null \
            && ok "paquete: ${pkg}" \
            || fail "paquete faltante: ${pkg}"
    done
}

# =============================================================================
check_env_file() {
    log_header "Archivo .env"

    if exists_file "$ENV_FILE"; then
        ok ".env encontrado: ${ENV_FILE}"
    else
        warn ".env no existe — copia desde .env.example"
    fi

    for var in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT SECRET_KEY; do
        [[ -n "${!var:-}" ]] \
            && ok "${var} definida" \
            || warn "${var} no definida en .env"
    done
}

# =============================================================================
check_database() {
    log_header "PostgreSQL"

    log_info "Host: ${POSTGRES_HOST}:${POSTGRES_PORT}"

    if tcp_is_reachable "$POSTGRES_HOST" "$POSTGRES_PORT" 3; then
        ok "PostgreSQL alcanzable en ${POSTGRES_HOST}:${POSTGRES_PORT}"
    else
        warn "PostgreSQL NO alcanzable — arranca con: sudo pg_ctlcluster 16 main start"
        return
    fi

    # Verificar conexion con credenciales Django
    local db_name="${DB_NAME:-practicayoruba_db}"
    local db_user="${DB_USER:-django_user}"
    local db_pass="${DB_PASSWORD:-django_pass}"

    PGPASSWORD="$db_pass" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" \
        -U "$db_user" -d "$db_name" -c "SELECT 1;" &>/dev/null \
        && ok "Conexion Django OK: ${db_user}@${db_name}" \
        || warn "No se pudo conectar como ${db_user} a ${db_name} — ejecuta db_setup.sh"
}

# =============================================================================
check_logs_dir() {
    log_header "Estructura del proyecto"

    local logs_dir="${PROJECT_ROOT}/practicayoruba/logs"
    exists_dir "$logs_dir" \
        && ok "logs/ existe" \
        || warn "logs/ no existe — Django no podra escribir logs de archivo"

    exists_file "${PROJECT_ROOT}/practicayoruba/manage.py" \
        && ok "manage.py encontrado" \
        || fail "manage.py no encontrado"

    exists_file "${PROJECT_ROOT}/practicayoruba/.env" \
        && ok ".env encontrado" \
        || warn ".env no encontrado"
}

# =============================================================================
# MAIN
# =============================================================================
log_separator 60 "="
echo "  PracticaYoruba API — Estado del entorno"
log_separator 60 "="
echo ""

check_system
check_venv
check_env_file
check_database
check_logs_dir

echo ""
log_separator 60 "-"
echo "  OK: ${OK}   WARN: ${WARNINGS}   ERROR: ${ERRORS}"
log_separator 60 "-"
echo ""

(( ERRORS > 0 )) && exit 1 || exit 0
