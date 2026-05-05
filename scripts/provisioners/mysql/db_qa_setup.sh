#!/bin/bash
# =============================================================================
# db_qa_setup.sh — MySQL: crea BD de QA (Unit Testing / Acceptance)
# =============================================================================
# IDEMPOTENTE. BD completamente separada de produccion.
#
# Uso:
#   sudo bash scripts/provisioners/mysql/db_qa_setup.sh
#   # o en contenedores sin sudo:
#   bash scripts/provisioners/mysql/db_qa_setup.sh
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
source "${PROJECT_ROOT}/scripts/utils/network.sh"
source "${PROJECT_ROOT}/scripts/utils/database.sh"

ENV_FILE="${PROJECT_ROOT}/practicayoruba/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

DB_NAME="${DB_QA_NAME:-practicayoruba_qa}"
DB_USER="${DB_QA_USER:-django_user}"
DB_PASSWORD="${DB_QA_PASSWORD:-django_pass}"
DB_HOST="${DB_QA_HOST:-127.0.0.1}"
DB_PORT="${DB_QA_PORT:-3306}"

TOTAL_STEPS=5

# Wrapper: intenta socket Unix primero, despues TCP
_my_exec() {
    local sock=""
    for s in /run/mysqld/mysqld.sock /var/run/mysqld/mysqld.sock; do
        if [[ -S "$s" ]] && mysqladmin --socket="$s" ping --silent >/dev/null 2>&1; then
            sock="$s"
            break
        fi
    done

    if [[ -n "$sock" ]]; then
        mysql --socket="$sock" --batch "$@" 2>&1
    else
        mysql -h "$DB_HOST" -P "$DB_PORT" --batch "$@" 2>&1
    fi
}

_my_exec_quiet() { _my_exec --silent --skip-column-names "$@" 2>/dev/null; }

# =============================================================================
check_prerequisites() {
    log_step 1 $TOTAL_STEPS "Verificando prerequisitos"

    command -v mysql &>/dev/null || { log_fatal "mysql client no encontrado"; exit 1; }

    if ! mysql_is_running "$DB_HOST" "$DB_PORT"; then
        log_warn "MySQL no responde — intentando arranque automatico"
        mysql_start || {
            log_fatal "MySQL no disponible en ${DB_HOST}:${DB_PORT}"
            log_fatal "Arranque manual: sudo bash scripts/provisioners/mysql/db_qa_setup.sh"
            exit 1
        }
    fi

    log_success "MySQL activo"
}

# =============================================================================
create_database() {
    log_step 2 $TOTAL_STEPS "Base de datos QA: ${DB_NAME}"

    local exists
    exists=$(_my_exec_quiet -e \
        "SELECT COUNT(*) FROM information_schema.SCHEMATA
         WHERE SCHEMA_NAME = '${DB_NAME}';" || echo "0")

    if [[ "$exists" -gt 0 ]]; then
        log_info "BD QA ya existe — sin cambios"
    else
        _my_exec -e \
            "CREATE DATABASE \`${DB_NAME}\`
             CHARACTER SET utf8mb4
             COLLATE utf8mb4_unicode_ci;" > /dev/null
        log_success "BD QA ${DB_NAME} creada"
    fi
}

# =============================================================================
grant_privileges() {
    log_step 3 $TOTAL_STEPS "Privilegios: ${DB_USER} sobre ${DB_NAME}"

    for host in "%" "localhost" "127.0.0.1"; do
        _my_exec -e \
            "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${host}';" > /dev/null
        # pytest necesita poder crear/borrar test_<DB_NAME>
        _my_exec -e \
            "GRANT ALL PRIVILEGES ON \`test_${DB_NAME}\`.* TO '${DB_USER}'@'${host}';" > /dev/null
    done

    _my_exec -e "FLUSH PRIVILEGES;" > /dev/null
    log_success "Privilegios aplicados (incluye test_${DB_NAME} para pytest)"
}

# =============================================================================
repair_system_tables() {
    log_step 4 $TOTAL_STEPS "Verificando tablas del sistema"

    # mysql.proc puede quedar corrupta en reinicios abruptos de contenedores
    local result
    result=$(_my_exec_quiet -e \
        "SELECT TABLE_NAME FROM information_schema.TABLES
         WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='proc';" || echo "")

    if [[ -n "$result" ]]; then
        _my_exec -e "REPAIR TABLE mysql.proc;" > /dev/null 2>&1 \
            && log_info "mysql.proc verificada/reparada" \
            || log_warn "mysql.proc no se pudo reparar — puede ignorarse en entornos de desarrollo"
    fi
}

# =============================================================================
verify_connection() {
    log_step 5 $TOTAL_STEPS "Verificando conexion Django → QA"

    local sock=""
    for s in /run/mysqld/mysqld.sock /var/run/mysqld/mysqld.sock; do
        [[ -S "$s" ]] && mysqladmin --socket="$s" ping --silent >/dev/null 2>&1 && sock="$s" && break
    done

    local result
    if [[ -n "$sock" ]]; then
        result=$(mysql --socket="$sock" \
            -u "$DB_USER" -p"${DB_PASSWORD}" \
            --batch --silent --skip-column-names \
            -e "SELECT CONCAT(DATABASE(), '@', USER());" \
            "$DB_NAME" 2>&1) || {
            log_error "No se pudo conectar via socket: $result"
            exit 1
        }
    else
        result=$(mysql -h "$DB_HOST" -P "$DB_PORT" \
            -u "$DB_USER" -p"${DB_PASSWORD}" \
            --batch --silent --skip-column-names \
            -e "SELECT CONCAT(DATABASE(), '@', USER());" \
            "$DB_NAME" 2>&1) || {
            log_error "No se pudo conectar via TCP: $result"
            exit 1
        }
    fi

    log_success "Conexion OK: ${result}"
}

# =============================================================================
log_header "MySQL QA Setup — PracticaYoruba API"
echo "  BD QA   : ${DB_NAME}"
echo "  Usuario : ${DB_USER}"
echo "  Host    : ${DB_HOST}:${DB_PORT}"
echo "  NOTA    : BD exclusiva para tests, separada de produccion"
echo ""

check_prerequisites
create_database
grant_privileges
repair_system_tables
verify_connection

echo ""
log_success "BD QA lista."
log_info "Siguiente: cd practicayoruba && DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py migrate"
