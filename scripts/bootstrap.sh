#!/bin/bash
# =============================================================================
# bootstrap.sh — PracticaYoruba API: setup y verificacion del entorno
# =============================================================================
# Uso:
#   sudo bash scripts/bootstrap.sh [--skip-update]
#
# Modelo de usuarios (D-031 H-24, ver Procedimiento-Implementacion-
# Almacenamiento-WSL2-ecomerce-p001 v1.0.0):
#   - INVOCADOR: deploy (cuenta sudoer). Ejecuta el script con sudo.
#   - RUNTIME:   develop (owner del repo). Quien usa manage.py / pytest
#                tras el bootstrap. NO debe correr este script
#                directamente — no tiene sudo y los apt-get fallarian
#                con permission denied criptico.
#   - PROVEEDOR: root (heredado via sudo). Instala paquetes, configura
#                MariaDB. El script chowna al final al repo OWNER
#                (develop) para que el runtime tenga write access.
#
# Cuentas en NO uso aqui (responsabilidad del provisioning de
# almacenamiento, D-030):
#   - infra, svc-backups, svc-dbdata
#
# Flujo:
#   Fase 1 — Sistema       : verifica Ubuntu 24.04
#   Fase 2 — Paquetes      : instala dependencias del sistema
#   Fase 3 — Python        : crea venv e instala requirements (uv)
#   Fase 4 — Base de datos : arranca MariaDB, crea BD produccion y BD QA
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

# D-031 H-24 (reportado por deploy@yollotl): si develop (no-sudoer)
# invoca bootstrap.sh directamente, los apt-get fallan con permission
# denied criptico despues de varios minutos. Fail loud al inicio con
# mensaje explicativo del modelo de usuarios.
if [[ "$(id -u)" -ne 0 ]]; then
    log_fatal "bootstrap.sh debe ejecutarse como root (via sudo)"
    log_error ""
    log_error "  Estas corriendo como: $(whoami) (UID $(id -u))"
    log_error ""
    log_error "  Modelo de usuarios del proyecto (D-030):"
    log_error "    deploy   — cuenta sudoer que invoca este script"
    log_error "    develop  — owner del repo, usa manage.py / pytest"
    log_error "               POST-bootstrap (no aqui)"
    log_error ""
    log_error "  Invocacion correcta:"
    log_error "    sudo bash scripts/bootstrap.sh"
    log_error ""
    log_error "  Si estas en develop sin sudo, cambia a deploy primero:"
    log_error "    su deploy"
    log_error "    cd ${PROJECT_ROOT}"
    log_error "    sudo bash scripts/bootstrap.sh"
    exit 1
fi

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

    # D-031 H-25: MARIADB_CLI / MARIADB_ADM se resolvieron al SOURCEAR
    # database.sh (linea ~32), ANTES de que mariadb-client estuviera
    # instalado. En el primer run bootstrap aparecen vacias y los
    # helpers como mariadb_is_running fallarian. Re-resolver
    # explicitamente AHORA que el paquete acaba de instalarse.
    MARIADB_CLI="$(mariadb_client_bin)"
    MARIADB_ADM="$(mariadb_admin_bin)"
    export MARIADB_CLI MARIADB_ADM
    log_info "  Re-resolucion CLI MariaDB: ${MARIADB_CLI:-(no encontrado)}"
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

    # D-031 H-23 (reportado deploy@yollotl): antes el script seguia
    # adelante con log_warn aunque db_setup fallara, declaraba
    # "Bootstrap completado" al final y verify reportaba 1 ERROR — pero
    # exit code 0 falseando el estado real. Ahora propagamos exit no-cero
    # si alguno de los provisioners critico falla (DEC-DOC-008). El
    # operador puede leer DB_PHASE_FAILED como flag al final.
    DB_PHASE_FAILED=false

    # 2. Configurar BDs y usuario
    if bash "${SCRIPT_DIR}/provisioners/mysql/db_setup.sh"; then
        log_success "MySQL configurado"
    else
        log_error "db_setup.sh fallo — revisa el output arriba"
        DB_PHASE_FAILED=true
    fi

    # 3. Configurar BD de QA para tests
    if bash "${SCRIPT_DIR}/provisioners/mysql/db_qa_setup.sh"; then
        log_success "BD QA configurada"
    else
        log_error "db_qa_setup.sh fallo — revisa el output arriba"
        DB_PHASE_FAILED=true
    fi

    if [[ "$DB_PHASE_FAILED" == "true" ]]; then
        log_error "Fase 4 de base de datos fallo. Migraciones y verify"
        log_error "no se ejecutaran. Resuelve el error y re-ejecuta."
        return 1
    fi
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
    # D-031 H-23: capturar fallo de phase_database para skip migrations
    # + reportar al final con exit code distinto de cero.
    BOOTSTRAP_FAILED=false
    if ! phase_database; then
        BOOTSTRAP_FAILED=true
    fi
    echo ""
    phase_migrations
    echo ""
    phase_verify

    # D-031 / H-18: bootstrap corre como root (sudo bash) y crea
    # artefactos en el filesystem (logs/, .venv/, .env). El usuario
    # que ejecuta manage.py despues NO es necesariamente $SUDO_USER:
    # en el modelo de 5 cuentas del procedimiento de almacenamiento
    # (D-030), deploy invoca sudo pero develop es quien edita codigo
    # y corre manage.py. Si chowneamos a deploy, develop sigue sin
    # poder escribir → mismo error PermissionError.
    #
    # Fix correcto: chown al OWNER del repo (PROJECT_ROOT), no a
    # SUDO_USER. El procedimiento garantiza que el repo es propiedad
    # del runtime-user (develop en WSL2/VPS con procedimiento;
    # ubuntu/practicayoruba en VPS estandar). Si el repo es root-owned
    # (clone como root sin chown), el script no toca nada — safe default.
    #
    # Reportado por deploy@yollotl: 'develop' (owner del repo) no
    # podia escribir logs/ tras sudo bootstrap.
    local repo_owner repo_group
    repo_owner=$(stat -c '%U' "$PROJECT_ROOT" 2>/dev/null) || repo_owner=""
    repo_group=$(stat -c '%G' "$PROJECT_ROOT" 2>/dev/null) || repo_group=""
    if [[ -n "$repo_owner" && "$repo_owner" != "root" ]]; then
        log_info "  Restaurando ownership a ${repo_owner}:${repo_group} (owner del repo)..."
        for path in "${PROJECT_ROOT}/.venv" \
                    "${PROJECT_ROOT}/practicayoruba/logs" \
                    "${PROJECT_ROOT}/practicayoruba/.env"; do
            [[ -e "$path" ]] && chown -R "${repo_owner}:${repo_group}" "$path"
        done
        log_success "  Ownership restaurado a ${repo_owner}:${repo_group}"
    else
        log_warn "  PROJECT_ROOT root-owned o sin stat — omitiendo chown post-bootstrap"
        log_warn "  Si manage.py falla con PermissionError en logs/:"
        log_warn "    sudo chown -R \$(stat -c '%U' \"$PROJECT_ROOT\"):\$(stat -c '%G' \"$PROJECT_ROOT\") \\"
        log_warn "      ${PROJECT_ROOT}/practicayoruba/logs ${PROJECT_ROOT}/.venv"
    fi

    log_separator 60 "="
    log_info "Tiempo total: $(show_elapsed)"
    # D-031 H-23: reportar estado real. Antes siempre decia "completado"
    # incluso con phases falladas.
    if [[ "${BOOTSTRAP_FAILED:-false}" == "true" ]]; then
        log_error "Bootstrap completado CON ERRORES."
        log_error "Revisa los mensajes ERR arriba y resuelve antes de"
        log_error "ejecutar tests o el servidor."
    else
        log_success "Bootstrap completado."
    fi
    echo ""
    log_info "Siguientes pasos:"
    log_info "  source .venv/bin/activate"
    log_info "  cd practicayoruba"
    log_info "  python manage.py createsuperuser"
    log_info "  python manage.py runserver"
    echo ""
    log_info "Para verificar el entorno:"
    log_info "  bash scripts/provisioners/system/check_tools.sh"
    log_info "Para correr tests:"
    log_info "  pytest tests/"
    echo ""

    # Exit con codigo distinto de cero si alguna phase critica fallo
    [[ "${BOOTSTRAP_FAILED:-false}" == "true" ]] && return 1
    return 0
}

main
