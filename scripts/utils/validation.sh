#!/bin/bash
# =============================================================================
# validation.sh — Funciones de validacion — PracticaYoruba API
# =============================================================================
# Depende de: logging.sh, core.sh
# =============================================================================

validate_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Este script debe ejecutarse como root (usa sudo)"
        return 1
    fi
    return 0
}

validate_ubuntu() {
    local required_prefix="${1:-24.04}"
    local os_release="/etc/os-release"

    [[ -f "$os_release" ]] || { log_error "No se encontro ${os_release}"; return 1; }

    local os_id os_version_id
    os_id=$(. "$os_release" && echo "${ID:-}")
    os_version_id=$(. "$os_release" && echo "${VERSION_ID:-}")

    [[ "${os_id,,}" == "ubuntu" ]] || { log_error "SO incompatible: ${os_id}"; return 1; }
    [[ "${os_version_id}" == "${required_prefix}"* ]] || {
        log_error "Version incompatible: Ubuntu ${os_version_id} (se requiere ${required_prefix}.x)"
        return 1
    }
    return 0
}

validate_python_version() {
    local required_major="${1:-3}" required_minor="${2:-11}"

    require_command python3 || return 1

    local major minor
    major=$(python3 -c "import sys; print(sys.version_info.major)")
    minor=$(python3 -c "import sys; print(sys.version_info.minor)")

    if (( major < required_major )) || (( major == required_major && minor < required_minor )); then
        log_error "Python ${major}.${minor} no cumple el minimo: ${required_major}.${required_minor}+"
        return 1
    fi
    return 0
}
