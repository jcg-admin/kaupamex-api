#!/bin/bash
# =============================================================================
# db_qa_setup.sh — MySQL: crea BD de QA (Unit Testing / Acceptance)
# =============================================================================
# IDEMPOTENTE. BD completamente separada de produccion.
#
# Uso:
#   sudo bash scripts/provisioners/mysql/db_qa_setup.sh
#
# Variables leidas desde practicayoruba/.env:
#   DB_QA_NAME      (default: practicayoruba_qa)
#   DB_QA_USER      (default: django_user)
#   DB_QA_PASSWORD  (default: django_pass)
#   DB_QA_HOST      (default: 127.0.0.1)
#   DB_QA_PORT      (default: 3306)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${PROJECT_ROOT}/scripts/utils/logging.sh"

ENV_FILE="${PROJECT_ROOT}/practicayoruba/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

DB_NAME="${DB_QA_NAME:-practicayoruba_qa}"
DB_USER="${DB_QA_USER:-django_user}"
DB_PASSWORD="${DB_QA_PASSWORD:-django_pass}"
DB_HOST="${DB_QA_HOST:-127.0.0.1}"
DB_PORT="${DB_QA_PORT:-3306}"

TOTAL_STEPS=4

my_root() { mysql --batch "$@" 2>&1; }
my_root_quiet() { mysql --batch --silent --skip-column-names "$@" 2>/dev/null; }

# =============================================================================
check_prerequisites() {
    log_step 1 $TOTAL_STEPS "Verificando prerequisitos"

    [[ $EUID -ne 0 ]] && { log_fatal "Ejecqa con sudo"; exit 1; }
    command -v mysql &>/dev/null || { log_fatal "mysql client no encontrado"; exit 1; }
    my_root_quiet -e "SELECT 1;" > /dev/null || {
        log_fatal "MySQL no responde en ${DB_HOST}:${DB_PORT}"
        exit 1
    }
    log_success "MySQL activo"
}

# =============================================================================
create_database() {
    log_step 2 $TOTAL_STEPS "Base de datos QA: ${DB_NAME}"

    local exists
    exists=$(my_root_quiet -e \
        "SELECT COUNT(*) FROM information_schema.SCHEMATA
         WHERE SCHEMA_NAME = '${DB_NAME}';" || echo "0")

    if [[ "$exists" -gt 0 ]]; then
        log_info "BD QA ya existe — sin cambios"
    else
        my_root -e \
            "CREATE DATABASE \`${DB_NAME}\`
             CHARACTER SET utf8mb4
             COLLATE utf8mb4_unicode_ci;" > /dev/null
        log_success "BD QA ${DB_NAME} creada"
    fi
}

# =============================================================================
grant_privileges() {
    log_step 3 $TOTAL_STEPS "Privilegios: ${DB_USER} sobre ${DB_NAME}"

    for host in "%" "localhost"; do
        my_root -e \
            "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${host}';" > /dev/null
    done

    my_root -e "FLUSH PRIVILEGES;" > /dev/null
    log_success "Privilegios aplicados"
}

# =============================================================================
verify_connection() {
    log_step 4 $TOTAL_STEPS "Verificando conexion Django → QA"

    local result
    result=$(mysql -h "$DB_HOST" -P "$DB_PORT" \
        -u "$DB_USER" -p"${DB_PASSWORD}" \
        --batch --silent --skip-column-names \
        -e "SELECT CONCAT(DATABASE(), '@', USER());" \
        "$DB_NAME" 2>&1) || {
        log_error "No se pudo conectar: $result"
        exit 1
    }

    log_success "Conexion OK: ${result}"
}

# =============================================================================
log_header "MySQL QA Setup — PracticaYoruba API"
echo "  BD QA  : ${DB_NAME}"
echo "  Usuario : ${DB_USER}"
echo "  Host    : ${DB_HOST}:${DB_PORT}"
echo "  NOTA    : BD exclusiva para tests, separada de produccion"
echo ""

check_prerequisites
create_database
grant_privileges
verify_connection

echo ""
log_success "BD QA lista."
log_info "Siguiente: cd practicayoruba && DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py migrate"
