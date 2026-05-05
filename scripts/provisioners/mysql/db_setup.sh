#!/bin/bash
# =============================================================================
# db_setup.sh — MySQL: crea BD y usuario para PracticaYoruba API
# =============================================================================
# IDEMPOTENTE: se puede ejecutar N veces sin efectos adversos.
#
# Uso:
#   sudo bash scripts/provisioners/mysql/db_setup.sh
#   # o en contenedores sin sudo:
#   bash scripts/provisioners/mysql/db_setup.sh
#
# Variables leidas desde practicayoruba/.env (con defaults):
#   DB_NAME      (default: practicayoruba_db)
#   DB_USER      (default: django_user)
#   DB_PASSWORD  (default: django_pass)
#   DB_HOST      (default: 127.0.0.1)
#   DB_PORT      (default: 3306)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${PROJECT_ROOT}/scripts/utils/logging.sh"
source "${PROJECT_ROOT}/scripts/utils/database.sh"

ENV_FILE="${PROJECT_ROOT}/practicayoruba/.env"
if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

DB_NAME="${DB_NAME:-practicayoruba_db}"
DB_USER="${DB_USER:-django_user}"
DB_PASSWORD="${DB_PASSWORD:-django_pass}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"

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

    command -v mysql &>/dev/null || { log_fatal "mysql client no encontrado. Instala mysql-client."; exit 1; }

    if ! mysql_is_running "$DB_HOST" "$DB_PORT"; then
        log_warn "MySQL no responde — intentando arranque automatico"
        mysql_start || {
            log_fatal "MySQL no disponible en ${DB_HOST}:${DB_PORT}"
            log_error "Arranque manual del servidor:"
            log_error "  sudo service mysql start"
            log_error "  # o en contenedores:"
            log_error "  sudo bash scripts/provisioners/mysql/db_setup.sh"
            exit 1
        }
    fi

    log_success "MySQL activo en ${DB_HOST}:${DB_PORT}"
}

# =============================================================================
create_database() {
    log_step 2 $TOTAL_STEPS "Base de datos: ${DB_NAME}"

    local exists
    exists=$(_my_exec_quiet -e \
        "SELECT COUNT(*) FROM information_schema.SCHEMATA
         WHERE SCHEMA_NAME = '${DB_NAME}';" || echo "0")

    if [[ "$exists" -gt 0 ]]; then
        log_info "Base de datos ya existe — sin cambios"
    else
        _my_exec -e \
            "CREATE DATABASE \`${DB_NAME}\`
             CHARACTER SET utf8mb4
             COLLATE utf8mb4_unicode_ci;" > /dev/null
        log_success "Base de datos ${DB_NAME} creada (utf8mb4)"
    fi
}

# =============================================================================
create_user() {
    log_step 3 $TOTAL_STEPS "Usuario: ${DB_USER}"

    for host in "%" "localhost" "127.0.0.1"; do
        local exists
        exists=$(_my_exec_quiet -e \
            "SELECT COUNT(*) FROM mysql.user
             WHERE User = '${DB_USER}' AND Host = '${host}';" || echo "0")

        if [[ "$exists" -gt 0 ]]; then
            _my_exec -e \
                "ALTER USER '${DB_USER}'@'${host}'
                 IDENTIFIED BY '${DB_PASSWORD}';" > /dev/null
            log_info "Usuario ${DB_USER}@${host} ya existe — contrasena sincronizada"
        else
            _my_exec -e \
                "CREATE USER '${DB_USER}'@'${host}'
                 IDENTIFIED BY '${DB_PASSWORD}';" > /dev/null
            log_success "Usuario ${DB_USER}@${host} creado"
        fi
    done
}

# =============================================================================
grant_privileges() {
    log_step 4 $TOTAL_STEPS "Privilegios: ${DB_USER} sobre ${DB_NAME}"

    local test_db="test_${DB_NAME}"

    for host in "%" "localhost" "127.0.0.1"; do
        # Produccion
        _my_exec -e \
            "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${host}';" > /dev/null
        # Tests: pytest necesita crear y destruir test_<DB_NAME>
        _my_exec -e \
            "GRANT ALL PRIVILEGES ON \`${test_db}\`.* TO '${DB_USER}'@'${host}';" > /dev/null
    done

    _my_exec -e "FLUSH PRIVILEGES;" > /dev/null
    log_success "Privilegios aplicados (incluye test_${DB_NAME} para pytest)"
}

# =============================================================================
verify_connection() {
    log_step 5 $TOTAL_STEPS "Verificando conexion con credenciales Django"

    local sock=""
    for s in /run/mysqld/mysqld.sock /var/run/mysqld/mysqld.sock; do
        [[ -S "$s" ]] && mysqladmin --socket="$s" ping --silent 2>/dev/null && sock="$s" && break
    done

    local result
    if [[ -n "$sock" ]]; then
        result=$(mysql --socket="$sock" \
            -u "$DB_USER" -p"${DB_PASSWORD}" \
            --batch --silent --skip-column-names \
            -e "SELECT CONCAT(DATABASE(), '@', USER());" \
            "$DB_NAME" 2>&1) || {
            log_error "No se pudo conectar como ${DB_USER} via socket"
            log_error "$result"
            exit 1
        }
    else
        result=$(mysql -h "$DB_HOST" -P "$DB_PORT" \
            -u "$DB_USER" -p"${DB_PASSWORD}" \
            --batch --silent --skip-column-names \
            -e "SELECT CONCAT(DATABASE(), '@', USER());" \
            "$DB_NAME" 2>&1) || {
            log_error "No se pudo conectar como ${DB_USER} via TCP"
            log_error "$result"
            exit 1
        }
    fi

    log_success "Conexion OK: ${result}"
}

# =============================================================================
log_header "MySQL DB Setup — PracticaYoruba API"
echo "  Base de datos : ${DB_NAME}"
echo "  Usuario       : ${DB_USER}"
echo "  Host          : ${DB_HOST}:${DB_PORT}"
echo ""

check_prerequisites
create_database
create_user
grant_privileges
verify_connection

echo ""
log_success "Setup completado. Siguiente: cd practicayoruba && python manage.py migrate"
