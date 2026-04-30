#!/bin/bash
# =============================================================================
# db_setup.sh — PostgreSQL: crea BD y usuario para PracticaYoruba API
# =============================================================================
# IDEMPOTENTE: se puede ejecutar N veces sin efectos adversos.
#
# Uso:
#   sudo bash scripts/provisioners/postgres/db_setup.sh
#
# Variables leidas desde practicayoruba/.env (con defaults):
#   DB_NAME      (default: practicayoruba_db)
#   DB_USER      (default: django_user)
#   DB_PASSWORD  (default: django_pass)
#   DB_HOST      (default: 127.0.0.1)
#   DB_PORT      (default: 5432)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${PROJECT_ROOT}/scripts/utils/logging.sh"

# Leer .env si existe
ENV_FILE="${PROJECT_ROOT}/practicayoruba/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

DB_NAME="${DB_NAME:-practicayoruba_db}"
DB_USER="${DB_USER:-django_user}"
DB_PASSWORD="${DB_PASSWORD:-django_pass}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"

TOTAL_STEPS=5

pg_super() {
    su -c "psql -v ON_ERROR_STOP=1 $*" postgres 2>&1
}

pg_super_quiet() {
    su -c "psql -v ON_ERROR_STOP=1 -tAq $*" postgres 2>/dev/null
}

# =============================================================================
check_prerequisites() {
    log_step 1 $TOTAL_STEPS "Verificando prerequisitos"

    [[ $EUID -ne 0 ]] && { log_fatal "Ejecuta con sudo"; exit 1; }

    command -v psql &>/dev/null \
        || { log_fatal "psql no encontrado. Instala postgresql-client."; exit 1; }

    if ! su -c "pg_isready -h ${DB_HOST} -p ${DB_PORT} -q" postgres 2>/dev/null; then
        log_fatal "PostgreSQL no responde en ${DB_HOST}:${DB_PORT}"
        log_error "Arranca el servicio: sudo pg_ctlcluster 16 main start"
        exit 1
    fi

    log_success "PostgreSQL activo en ${DB_HOST}:${DB_PORT}"
}

# =============================================================================
create_user() {
    log_step 2 $TOTAL_STEPS "Usuario: ${DB_USER}"

    local exists
    exists=$(pg_super_quiet -c \
        "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}';" || echo "")

    if [[ "$exists" == "1" ]]; then
        pg_super -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" > /dev/null
        log_info "Usuario ya existe — contrasena sincronizada"
    else
        pg_super -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" > /dev/null
        log_success "Usuario ${DB_USER} creado"
    fi
}

# =============================================================================
create_database() {
    log_step 3 $TOTAL_STEPS "Base de datos: ${DB_NAME}"

    local exists
    exists=$(pg_super_quiet -c \
        "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}';" || echo "")

    if [[ "$exists" == "1" ]]; then
        log_info "Base de datos ya existe — sin cambios"
    else
        pg_super -c \
            "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER} ENCODING 'UTF8';" > /dev/null
        log_success "Base de datos ${DB_NAME} creada"
    fi
}

# =============================================================================
grant_privileges() {
    log_step 4 $TOTAL_STEPS "Privilegios: ${DB_USER} sobre ${DB_NAME}"

    pg_super -d "$DB_NAME" <<SQL > /dev/null
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO ${DB_USER};
ALTER ROLE ${DB_USER} CREATEDB;
SQL

    log_success "Privilegios aplicados (incluye CREATEDB para tests)"
}

# =============================================================================
verify_connection() {
    log_step 5 $TOTAL_STEPS "Verificando conexion con credenciales Django"

    local result
    result=$(PGPASSWORD="$DB_PASSWORD" \
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -tAq -c "SELECT current_database() || '@' || current_user;" 2>&1) || {
        log_error "No se pudo conectar como ${DB_USER}"
        log_error "$result"
        exit 1
    }

    log_success "Conexion OK: ${result}"
}

# =============================================================================
log_header "PostgreSQL DB Setup — PracticaYoruba API"
echo "  Base de datos : ${DB_NAME}"
echo "  Usuario       : ${DB_USER}"
echo "  Host          : ${DB_HOST}:${DB_PORT}"
echo ""

check_prerequisites
create_user
create_database
grant_privileges
verify_connection

echo ""
log_success "Setup completado. Siguiente: cd practicayoruba && python manage.py migrate"
