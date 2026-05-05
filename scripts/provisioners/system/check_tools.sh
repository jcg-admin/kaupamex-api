#!/bin/bash
# =============================================================================
# check_tools.sh — Verifica el estado del entorno — PracticaYoruba API
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${PROJECT_ROOT}/scripts/utils/logging.sh"
source "${PROJECT_ROOT}/scripts/utils/core.sh"
source "${PROJECT_ROOT}/scripts/utils/network.sh"
source "${PROJECT_ROOT}/scripts/utils/database.sh"

VENV_PYTHON="${PROJECT_ROOT}/venv/bin/python3"
if exists_file "$VENV_PYTHON"; then
    export PATH="${PROJECT_ROOT}/venv/bin:${PATH}"
fi

ENV_FILE="${PROJECT_ROOT}/practicayoruba/.env"
if exists_file "$ENV_FILE"; then
    set -a; source "$ENV_FILE"; set +a
fi

MYSQL_HOST="${DB_HOST:-127.0.0.1}"
MYSQL_PORT="${DB_PORT:-3306}"

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

    command_exists mysql \
        && ok "mysql: $(mysql --version 2>&1 | head -1)" \
        || warn "mysql client no encontrado (instala mysql-client)"
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

    for pkg in django djangorestframework MySQLdb rest_framework_simplejwt; do
        "${PROJECT_ROOT}/venv/bin/python3" -c "import ${pkg}" 2>/dev/null \
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
    log_header "MySQL / MariaDB"

    log_info "Host configurado: ${MYSQL_HOST}:${MYSQL_PORT}"

    # 1. Verificar via socket Unix (entornos sin red / contenedores)
    local socket_ok=false
    for sock in /run/mysqld/mysqld.sock /var/run/mysqld/mysqld.sock; do
        if [[ -S "$sock" ]]; then
            if mysqladmin --socket="$sock" ping --silent 2>/dev/null; then
                ok "MySQL alcanzable via socket: ${sock}"
                socket_ok=true
                break
            else
                warn "Socket existe pero no responde (posible archivo stale): ${sock}"
                warn "  Limpieza: bash scripts/provisioners/mysql/db_qa_setup.sh"
            fi
        fi
    done

    # 2. Si socket fallo, verificar via TCP
    if ! $socket_ok; then
        if tcp_is_reachable "$MYSQL_HOST" "$MYSQL_PORT" 3; then
            ok "MySQL alcanzable via TCP: ${MYSQL_HOST}:${MYSQL_PORT}"
        else
            warn "MySQL NO alcanzable ni via socket ni TCP"
            warn "  Opciones de arranque:"
            warn "  Con systemd : sudo service mysql start"
            warn "  Sin systemd : bash scripts/provisioners/mysql/db_qa_setup.sh"
            return
        fi
    fi

    # 3. Verificar conexion con credenciales Django
    local db_name="${DB_NAME:-practicayoruba_db}"
    local db_user="${DB_USER:-django_user}"
    local db_pass="${DB_PASSWORD:-django_pass}"
    local connected=false

    # Intentar socket
    for sock in /run/mysqld/mysqld.sock /var/run/mysqld/mysqld.sock; do
        if [[ -S "$sock" ]]; then
            mysql --socket="$sock" \
                -u "$db_user" -p"${db_pass}" \
                -e "SELECT 1;" "$db_name" &>/dev/null && {
                ok "Conexion Django OK (socket): ${db_user}@${db_name}"
                connected=true
                break
            }
        fi
    done

    # Fallback TCP
    if ! $connected; then
        mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" \
            -u "$db_user" -p"${db_pass}" \
            -e "SELECT 1;" "$db_name" &>/dev/null \
            && ok "Conexion Django OK (TCP): ${db_user}@${db_name}" \
            || warn "No se pudo conectar como ${db_user} a ${db_name} — ejecuta db_setup.sh"
    fi
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
