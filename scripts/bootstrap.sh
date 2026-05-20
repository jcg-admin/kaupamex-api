#!/bin/bash
# =============================================================================
# bootstrap.sh — PracticaYoruba API: setup y verificacion del entorno
# =============================================================================
# Uso:
#   sudo bash scripts/bootstrap.sh [--skip-update]
#
# Flujo:
#   Fase 1 — Sistema       : verifica Ubuntu 24.04
#   Fase 2 — Paquetes      : instala dependencias del sistema
#   Fase 3 — Python        : crea venv e instala requirements
#   Fase 4 — Base de datos : arranca MySQL, crea BD produccion y BD QA
#   Fase 5 — Migraciones   : ejecqa manage.py migrate
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

init_log "bootstrap"

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

    # D-031 / H-12: en Ubuntu 24.04 noble el paquete 'mysql-client'
    # instala Oracle MySQL 8.0 (no MariaDB). Esto:
    #   1. Conflicta con mariadb-client (apt remueve uno al instalar el otro)
    #   2. Provoca que el CLI 'mysql' apunte a MySQL 8.0 incompatible con
    #      MariaDB 11.8 server (D-028: en 11.x el CLI es 'mariadb')
    #   3. Si el operador instalo mariadb-server antes, apt lo desinstala
    #      al instalar mysql-client (cascada confirmada por deploy@yollotl).
    # Usar mariadb-client + libmariadb-dev — consistente con D-028.
    install_apt_packages \
        python3 python3-dev python3-venv python3-pip \
        build-essential pkg-config \
        libmariadb-dev mariadb-client \
        curl git
}

# =============================================================================
phase_python() {
    log_header "Fase 3/6 — Entorno Python"

    validate_python_version 3 11 || {
        log_fatal "Se requiere Python 3.11+"
        exit 1
    }

    local venv_dir="${PROJECT_ROOT}/.venv"
    local requirements="${PROJECT_ROOT}/requirements/development.txt"

    setup_venv "$venv_dir" "$requirements"

    "${venv_dir}/bin/python3" -c "import MySQLdb" 2>/dev/null \
        && log_success "mysqlclient OK" \
        || { log_fatal "mysqlclient no disponible — revisa default-libmysqlclient-dev"; exit 1; }
}

# =============================================================================
phase_database() {
    log_header "Fase 4/6 — Base de datos"

    # 1. Arrancar MySQL (incluye limpieza de estado stale y fallback sin systemd)
    if ! mysql_start; then
        log_warn "MySQL no pudo arrancar automaticamente"
        log_warn "Opciones manuales:"
        log_warn "  Con systemd : sudo service mysql start"
        log_warn "  Sin systemd : ver README — seccion 'Entornos sin systemd'"
        log_warn "Continuando — db_setup.sh fallara si MySQL no esta disponible"
    fi

    echo ""

    # 2. Configurar BDs y usuario (el script valida y arranca si es necesario)
    bash "${SCRIPT_DIR}/provisioners/mysql/db_setup.sh" && \
        log_success "MySQL configurado" || \
        log_warn "db_setup.sh reporto advertencias — revisa el output"

    # 3. Configurar BD de QA para tests
    bash "${SCRIPT_DIR}/provisioners/mysql/db_qa_setup.sh" && \
        log_success "BD QA configurada" || \
        log_warn "db_qa_setup.sh reporto advertencias"
}

# =============================================================================
phase_migrations() {
    log_header "Fase 5/6 — Migraciones Django"

    local python="${PROJECT_ROOT}/.venv/bin/python3"
    local manage="${PROJECT_ROOT}/practicayoruba/manage.py"

    if ! exists_file "$manage"; then
        log_warn "manage.py no encontrado en ${manage}"
        return 0
    fi

    if ! mysql_is_running; then
        log_warn "MySQL no disponible — omitiendo migraciones"
        return 0
    fi

    local env_file="${PROJECT_ROOT}/practicayoruba/.env"
    if ! exists_file "$env_file"; then
        # D-031 / H-15: auto-crear .env desde .env.example. Antes el
        # script salia con warn y exigia copia manual — el operador
        # tenia que recordar el paso. Ahora idempotente: si .env existe
        # se preserva; si no, se copia desde .env.example.
        local env_example="${PROJECT_ROOT}/practicayoruba/.env.example"
        if exists_file "$env_example"; then
            log_info ".env no existe — copiando desde .env.example..."
            cp "$env_example" "$env_file"
            log_success ".env creado: ${env_file}"
            log_warn "  Revisa SECRET_KEY antes de usar en produccion"
        else
            log_warn ".env y .env.example no existen — omitiendo migraciones"
            return 0
        fi
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

    # D-031 / H-18: bootstrap corre como root (sudo bash) y crea
    # artefactos en el filesystem (logs/, .venv/, .env). El usuario
    # invocador (SUDO_USER, p.ej. develop) necesita escribir en logs/
    # cuando ejecute manage.py migrate / runserver post-bootstrap. Si
    # quedan owned por root, manage.py revienta con
    # PermissionError: '...practicayoruba/logs/django.log'.
    # Reportado por deploy@yollotl.
    #
    # Restaurar ownership al usuario invocador (idempotente: chown
    # repeat sobre archivos del usuario no tiene efecto).
    if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
        local sudo_uid sudo_gid
        sudo_uid=$(id -u "$SUDO_USER" 2>/dev/null) || sudo_uid=""
        sudo_gid=$(id -g "$SUDO_USER" 2>/dev/null) || sudo_gid=""
        if [[ -n "$sudo_uid" && -n "$sudo_gid" ]]; then
            log_info "  Restaurando ownership a ${SUDO_USER}:${SUDO_USER}..."
            for path in "${PROJECT_ROOT}/.venv" \
                        "${PROJECT_ROOT}/practicayoruba/logs" \
                        "${PROJECT_ROOT}/practicayoruba/.env"; do
                [[ -e "$path" ]] && chown -R "${sudo_uid}:${sudo_gid}" "$path"
            done
            log_success "  Ownership restaurado"
        fi
    fi

    log_separator 60 "="
    log_info "Tiempo total: $(show_elapsed)"
    log_success "Bootstrap completado."
    echo ""
    log_info "Siguientes pasos:"
    log_info "  source .venv/bin/activate"
    log_info "  cd practicayoruba"
    log_info "  python manage.py createsuperuser"
    log_info "  python manage.py runserver"
    echo ""
    log_info "Para verificar el entorno:"
    log_info "  bash scripts/provisioners/system/check_tools.sh"
    echo ""
}

main
