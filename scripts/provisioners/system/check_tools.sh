#!/bin/bash
# =============================================================================
# check_tools.sh — Verifica el estado del entorno — kaupamex-api
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

source "${PROJECT_ROOT}/scripts/utils/logging.sh"
source "${PROJECT_ROOT}/scripts/utils/core.sh"
source "${PROJECT_ROOT}/scripts/utils/network.sh"
source "${PROJECT_ROOT}/scripts/utils/postgresql.sh"

# D-031: convencion actual es .venv; fallback a venv si existe (legacy)
if [[ -x "${PROJECT_ROOT}/.venv/bin/python3" ]]; then
    VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python3"
elif [[ -x "${PROJECT_ROOT}/venv/bin/python3" ]]; then
    VENV_PYTHON="${PROJECT_ROOT}/venv/bin/python3"
else
    VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python3"
fi
if exists_file "$VENV_PYTHON"; then
    export PATH="${PROJECT_ROOT}/.venv/bin:${PROJECT_ROOT}/venv/bin:${PATH}"
fi

ENV_FILE="${PROJECT_ROOT}/src/.env"
if exists_file "$ENV_FILE"; then
    set -a; source "$ENV_FILE"; set +a
fi

PG_HOST="${DB_SOCKET:-${DB_HOST:-/var/run/postgresql}}"
PG_PORT="${DB_PORT:-5432}"

ERRORS=0; WARNINGS=0; OK=0

ok()   { log_success "$1"; OK=$(( OK + 1 ))   || true; }
warn() { log_warn "$1";    WARNINGS=$(( WARNINGS + 1 )) || true; }
fail() { log_error "$1";   ERRORS=$(( ERRORS + 1 ))   || true; }

# =============================================================================
check_system() {
    log_header "Sistema"

    command_exists python3 \
        && ok "python3: $(python3 --version 2>&1)" \
        || fail "python3 no encontrado"

    # Motor PostgreSQL (ADR-028). El cliente lo trae postgresql-client:
    # psql para consultas y pg_isready como gate de disponibilidad.
    # el canonico cuando esta disponible.
    if command_exists psql; then
        ok "psql: $(psql --version 2>&1 | head -1)"
    else
        warn "psql no encontrado (instala postgresql-client)"
    fi
}

# =============================================================================
check_venv() {
    log_header "Entorno virtual"

    # D-031 / H-13: la convencion del repo es .venv (no venv) — sync
    # con server/.env.example y D-030. Acepta ambos para backwards-compat.
    local venv_dir=""
    if exists_dir "${PROJECT_ROOT}/.venv"; then
        venv_dir="${PROJECT_ROOT}/.venv"
        ok "venv existe: ${venv_dir}"
    elif exists_dir "${PROJECT_ROOT}/venv"; then
        venv_dir="${PROJECT_ROOT}/venv"
        warn "venv legacy en ${venv_dir} — convencion actual es .venv"
    else
        warn "venv no existe — ejecuta: uv sync  (crea .venv desde pyproject.toml + uv.lock)"
        return
    fi

    # D-031 / H-16: el nombre importable de DRF es 'rest_framework',
    # NO 'djangorestframework'. El check anterior siempre fallaba
    # falso-positivo aun con DRF correctamente instalado. Mismo
    # El driver es psycopg 3 (pyproject: psycopg[binary] >=3.2).
    for pkg in django rest_framework psycopg rest_framework_simplejwt; do
        "${venv_dir}/bin/python3" -c "import ${pkg}" 2>/dev/null \
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

    # En libpq el socket ES el HOST: un HOST que empieza con '/' designa el
    # DIRECTORIO del socket y el PORT nombra el archivo (.s.PGSQL.5432). Por
    # eso aqui no hay una rama "socket" y otra "TCP" como tenia la version de
    # MariaDB — es el mismo parametro con distinto valor (H-API-305).
    log_info "Host configurado: ${PG_HOST}:${PG_PORT}"

    if ! command_exists pg_isready; then
        warn "pg_isready no disponible — instala postgresql-client"
        return
    fi

    if pg_isready -h "$PG_HOST" -p "$PG_PORT" >/dev/null 2>&1; then
        ok "PostgreSQL responde: ${PG_HOST}:${PG_PORT}"
    else
        warn "PostgreSQL NO responde en ${PG_HOST}:${PG_PORT}"
        warn "  Arranque (Debian opera por cluster, no por proceso suelto):"
        warn "    sudo pg_ctlcluster 16 main start"
        warn "    pg_lsclusters      # estado de los clusters registrados"
        return
    fi

    # Conexion con las credenciales de Django.
    local db_name="${DB_NAME:-kaupamex_db}"
    local db_user="${DB_USER:-django_user}"

    if PGPASSWORD="${DB_PASSWORD:-}" psql -h "$PG_HOST" -p "$PG_PORT" \
            -U "$db_user" -d "$db_name" -tAc "SELECT 1" >/dev/null 2>&1; then
        ok "Conexion Django OK: ${db_user}@${db_name}"
    else
        warn "No se pudo conectar como ${db_user} a ${db_name}"
        warn "  Un 'Peer authentication failed' NO es de credenciales: el"
        warn "  pg_hba.conf de Debian asigna 'peer' al canal local y el rol"
        warn "  de aplicacion necesita su regla explicita (H-DB-05). La"
        warn "  instala: db/provisioners/postgresql/db_setup.sh"
    fi
}

# =============================================================================
check_logs_dir() {
    log_header "Estructura del proyecto"

    local logs_dir="${PROJECT_ROOT}/src/logs"
    exists_dir "$logs_dir" \
        && ok "logs/ existe" \
        || warn "logs/ no existe — Django no podra escribir logs de archivo"

    exists_file "${PROJECT_ROOT}/kaupamex-bin" \
        && ok "kaupamex-bin encontrado" \
        || fail "kaupamex-bin no encontrado"

    exists_file "${PROJECT_ROOT}/src/.env" \
        && ok ".env encontrado" \
        || warn ".env no encontrado"
}

# =============================================================================
log_separator 60 "="
echo "  kaupamex-api — Estado del entorno"
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

if (( ERRORS > 0 )); then exit 1; fi
