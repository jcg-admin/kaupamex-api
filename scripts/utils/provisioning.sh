#!/bin/bash
# =============================================================================
# provisioning.sh — Funciones de aprovisionamiento — PracticaYoruba API
# =============================================================================
# Depende de: logging.sh, core.sh
# =============================================================================

apt_update() {
    if [[ "${SKIP_APT_UPDATE:-false}" == "true" ]]; then
        log_info "apt-get update omitido (--skip-update activo)"
        return 0
    fi
    log_info "Ejecutando apt-get update..."
    apt-get update -qq 2>&1 | tail -2
}

check_apt_package() {
    dpkg -l "$1" 2>/dev/null | grep -q "^ii"
}

install_apt_packages() {
    local to_install=()
    for pkg in "$@"; do
        check_apt_package "$pkg" \
            && log_info "Ya instalado: ${pkg}" \
            || to_install+=("$pkg")
    done

    (( ${#to_install[@]} == 0 )) && { log_success "Todos los paquetes ya estaban instalados"; return 0; }

    log_info "Instalando: ${to_install[*]}"
    apt-get install -y --no-install-recommends "${to_install[@]}" 2>&1 | tail -4
    log_success "Paquetes instalados"
}

setup_venv() {
    local venv_dir="$1" requirements="$2"

    if exists_dir "$venv_dir"; then
        log_info "Entorno virtual ya existe: ${venv_dir}"
    else
        log_info "Creando entorno virtual en ${venv_dir}..."
        python3 -m venv "$venv_dir"
        log_success "Entorno virtual creado"
    fi

    if exists_file "$requirements"; then
        log_info "Instalando dependencias desde ${requirements}..."
        "${venv_dir}/bin/pip" install --quiet --upgrade pip
        "${venv_dir}/bin/pip" install --quiet -r "$requirements"
        log_success "Dependencias instaladas"
    else
        log_warn "No se encontro: ${requirements}"
    fi
}
