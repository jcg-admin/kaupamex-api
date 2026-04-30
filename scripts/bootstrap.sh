#!/bin/bash
# =============================================================================
# bootstrap.sh — PracticaYoruba API: setup y verificacion del entorno
# =============================================================================
# Un solo comando para todo:
#   sudo bash scripts/bootstrap.sh
#
# Flags:
#   --skip-update   Omite apt-get update
#
# Flujo:
#   Fase 1 — Sistema       : verifica Ubuntu 24.04
#   Fase 2 — Paquetes      : instala dependencias del sistema
#   Fase 3 — Python        : crea venv e instala requirements
#   Fase 4 — Base de datos : arranca PostgreSQL y crea BD/usuario
#   Fase 5 — Migraciones   : ejecuta manage.py migrate
#   Fase 6 — Verificacion  : estado completo del entorno
# =============================================================================
set -euo pipefail

SKIP_APT_UPDATE=false
for arg in "$@"; do
    [[ "$arg" == "--skip-update" ]] && SKIP_APT_UPDATE=true
done
export SKIP_APT_UPDATE

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PROJECT_ROOT

source "${SCRIPT_DIR}/utils/logging.sh"
source "${SCRIPT_DIR}/utils/core.sh"
source "${SCRIPT_DIR}/utils/validation.sh"
source "${SCRIPT_DIR}/utils/network.sh"
source "${SCRIPT_DIR}/utils/database.sh"
source "${SCRIPT_DIR}/utils/provisioning.sh"

LOG_NAME="bootstrap"
init_log "$LOG_NAME"

# =============================================================================
phase_os() {
    log_header "Fase 1/6 — Sistema operativo"

    validate_ubuntu "24.04" || {
        log_fatal "SO incompatible — solo Ubuntu 24.04.x LTS"
        exit 1
    }

    log_success "Ubuntu 24.04 confirmado"
}

# =============================================================================
phase_packages() {
    log_header "Fase 2/6 — Paquetes del sistema"

    validate_root || {
        log_fatal "Requiere root. Usa: sudo bash scripts/bootstrap.sh"
        exit 1
    }

    apt_update

    install_apt_packages \
        python3 python3-dev python3-venv python3-pip \
        build-essential pkg-config \
        libpq-dev postgresql-client \
        curl git
}

# =============================================================================
phase_python() {
    log_header "Fase 3/6 — Entorno Python"

    validate_python_version 3 11 || {
        log_fatal "Se requiere Python 3.11+"
        exit 1
    }

    local venv_dir="${PROJECT_ROOT}/venv"
    local requirements="${PROJECT_ROOT}/requirements/development.txt"

    setup_venv "$venv_dir" "$requirements"

    # Verificar drivers criticos
    "${venv_dir}/bin/python3" -c "import psycopg2" 2>/dev/null \
        && log_success "psycopg2 OK" \
        || { log_fatal "psycopg2 no disponible — revisa libpq-dev"; exit 1; }
}

# =============================================================================
phase_database() {
    log_header "Fase 4/6 — Base de datos"

    # Arrancar PostgreSQL si esta caido
    pg_start 16 main || log_warn "No se pudo arrancar PostgreSQL automaticamente"

    echo ""
    if pg_is_running; then
        bash "${SCRIPT_DIR}/provisioners/postgres/db_setup.sh" && \
            log_success "PostgreSQL configurado" || \
            log_warn "db_setup.sh tuvo advertencias"
    else
        log_warn "PostgreSQL no disponible — configura manualmente"
        log_warn "  sudo pg_ctlcluster 16 main start"
        log_warn "  sudo bash scripts/provisioners/postgres/db_setup.sh"
    fi
}

# =============================================================================
phase_migrations() {
    log_header "Fase 5/6 — Migraciones Django"

    local python="${PROJECT_ROOT}/venv/bin/python3"
    local manage="${PROJECT_ROOT}/practicayoruba/manage.py"

    if ! exists_file "$manage"; then
        log_warn "manage.py no encontrado en ${manage}"
        return 0
    fi

    if ! pg_is_running; then
        log_warn "PostgreSQL no disponible — omitiendo migraciones"
        return 0
    fi

    local env_file="${PROJECT_ROOT}/practicayoruba/.env"
    if ! exists_file "$env_file"; then
        log_warn ".env no existe — copia desde .env.example antes de migrar"
        return 0
    fi

    DJANGO_SETTINGS_MODULE=config.settings.development \
    PYTHONPATH="${PROJECT_ROOT}/practicayoruba" \
    "$python" "$manage" migrate 2>&1 | tail -5 \
        && log_success "Migraciones aplicadas" \
        || log_warn "Migraciones con errores — revisa el output"
}

# =============================================================================
phase_verify() {
    log_header "Fase 6/6 — Verificacion del entorno"
    bash "${SCRIPT_DIR}/provisioners/system/check_tools.sh" || \
        log_warn "check_tools reporto advertencias"
}

# =============================================================================
main() {
    start_timer

    echo ""
    log_separator 60 "="
    echo "  PracticaYoruba API — Bootstrap"
    echo "  sudo bash scripts/bootstrap.sh [--skip-update]"
    [[ "$SKIP_APT_UPDATE" == "true" ]] && echo "  (--skip-update activo)"
    log_separator 60 "="
    echo ""

    phase_os
    echo ""
    phase_packages
    echo ""
    phase_python
    echo ""
    phase_database
    echo ""
    phase_migrations
    echo ""
    phase_verify

    log_separator 60 "="
    log_info "Tiempo total: $(show_elapsed)"
    log_success "Bootstrap completado."
    echo ""
    log_info "Siguientes pasos:"
    log_info "  source venv/bin/activate"
    log_info "  cd practicayoruba"
    log_info "  python manage.py createsuperuser"
    log_info "  python manage.py runserver"
    echo ""
    log_info "Para verificar el entorno en cualquier momento:"
    log_info "  bash scripts/provisioners/system/check_tools.sh"
    echo ""
}

main
