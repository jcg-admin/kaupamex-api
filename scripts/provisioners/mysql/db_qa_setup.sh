#!/bin/bash
# =============================================================================
# RETIRADO — motor MariaDB (ADR-028, 2026-08-06). NO sirve a ningún entorno.
# =============================================================================
# `bootstrap.sh` dejó de invocarlo: la Fase 4 delega el provisioning en
# `kaupamex-db` (`provisioners/postgresql/db_setup.sh [--qa]`), que es donde
# vive el motor en uso. Este archivo sigue en el repo porque lo citan docs,
# el runbook E2E de `ui`, `db/scripts/sync-and-test.sh` y ADR-004 — no porque
# algo lo ejecute. Retirarlo exige limpiar antes esas citas: sucesor
# registrado en H-API-385. No editar para "actualizarlo": el motor cambió.
# =============================================================================
# =============================================================================
# db_qa_setup.sh — MariaDB: crea BD de QA (Unit Testing / Acceptance)
# =============================================================================
# IDEMPOTENTE. BD completamente separada de produccion.
#
# Uso:
#   sudo bash scripts/provisioners/mysql/db_qa_setup.sh
#
# Modelo de usuarios (D-031 H-24, ver Procedimiento-Implementacion-
# Almacenamiento-WSL2-ecomerce-p001 v1.0.0):
#   - INVOCADOR: deploy via sudo (acceso al socket como root).
#   - NO RUN AS develop: sin sudo el script aborta loud.
#   - NO RUN AS infra: 'bash' no esta en la whitelist NOPASSWD de
#     infra; 'sudo bash db_qa_setup.sh' falla. Usar deploy.
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

# D-031 H-24: validar root al inicio (loud fail antes de cualquier
# operacion). Sin sudo el socket-auth como root falla con un
# 'Access denied' ambiguo.
if [[ "$(id -u)" -ne 0 ]]; then
    log_fatal "db_qa_setup.sh debe ejecutarse como root (via sudo)"
    log_error "  Estas corriendo como: $(whoami) (UID $(id -u))"
    log_error "  Usa: sudo bash scripts/provisioners/mysql/db_qa_setup.sh"
    exit 1
fi

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
        if [[ -S "$s" ]] && "${MARIADB_ADM:-mariadb-admin}" --socket="$s" ping --silent >/dev/null 2>&1; then
            sock="$s"
            break
        fi
    done

    if [[ -n "$sock" ]]; then
        "${MARIADB_CLI:-mariadb}" --socket="$sock" --batch "$@" 2>&1
    else
        "${MARIADB_CLI:-mariadb}" -h "$DB_HOST" -P "$DB_PORT" --batch "$@" 2>&1
    fi
}

_my_exec_quiet() { _my_exec --silent --skip-column-names "$@" 2>/dev/null; }

# =============================================================================
check_prerequisites() {
    log_step 1 $TOTAL_STEPS "Verificando prerequisitos"

    # D-031 H-17: ver db_setup.sh; MARIADB_CLI resuelto en utils/database.sh.
    [[ -n "${MARIADB_CLI:-}" ]] || { log_fatal "Cliente MariaDB no encontrado (ni mariadb ni mysql). Instala mariadb-client."; exit 1; }

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

    # D-031 H-22 (reportado deploy@yollotl): pre-crear las dos BDs que
    # pytest-django puede usar:
    #   - practicayoruba_qa: testing.py declara TEST.NAME=practicayoruba_qa
    #     (Django usa esta BD directamente como test database)
    #   - test_practicayoruba_qa: si alguien quita el override TEST.NAME,
    #     Django crea test_<DB_NAME> por convencion default
    # Pre-crear ambas + grant ALL evita necesidad de GRANT CREATE/DROP
    # ON *.* a django_user. Combinado con --reuse-db en pytest.ini
    # (H-21), elimina los cuelgues en DROP+CREATE.
    for db in "${DB_NAME}" "test_${DB_NAME}"; do
        _my_exec -e \
            "CREATE DATABASE IF NOT EXISTS \`${db}\`
             CHARACTER SET utf8mb4
             COLLATE utf8mb4_unicode_ci;" > /dev/null
    done
    log_info "  Pre-creadas: ${DB_NAME} y test_${DB_NAME} (anti-hang H-22)"

    for host in "%" "localhost" "127.0.0.1"; do
        _my_exec -e \
            "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${host}';" > /dev/null
        # pytest necesita poder crear/borrar test_<DB_NAME>; GRANT ALL
        # incluye CREATE/DROP DENTRO de esa BD (suficiente para
        # migrate/flush) pero NO CREATE/DROP DATABASE global.
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
        [[ -S "$s" ]] && "${MARIADB_ADM:-mariadb-admin}" --socket="$s" ping --silent >/dev/null 2>&1 && sock="$s" && break
    done

    local result
    if [[ -n "$sock" ]]; then
        result=$("${MARIADB_CLI:-mariadb}" --socket="$sock" \
            -u "$DB_USER" -p"${DB_PASSWORD}" \
            --batch --silent --skip-column-names \
            -e "SELECT CONCAT(DATABASE(), '@', USER());" \
            "$DB_NAME" 2>&1) || {
            log_error "No se pudo conectar via socket: $result"
            exit 1
        }
    else
        result=$("${MARIADB_CLI:-mariadb}" -h "$DB_HOST" -P "$DB_PORT" \
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
