#!/bin/bash
# =============================================================================
# provisioning.sh — Funciones de aprovisionamiento — kaupamex-api
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
    local project_root; project_root="$(dirname "$venv_dir")"

    # D-031 / H-14: el equipo usa uv como gestor de toolchain Python.
    # Detectar e instalar idempotentemente si falta. Caer a pip si la
    # instalacion de uv falla (sin red, --skip-update, etc.).
    _ensure_uv_installed || true

    # Modelo-proyecto uv: si existe pyproject.toml, esa es la fuente unica
    # de verdad de las dependencias. `uv sync` crea el .venv y lo
    # deja identico a uv.lock (reproducible). Es la ruta canonica del API.
    if exists_file "${project_root}/pyproject.toml" && command_exists uv; then
        log_info "Sincronizando entorno con uv sync (pyproject.toml + uv.lock)..."
        if ( cd "$project_root" && uv sync --quiet ); then
            log_success "uv sync OK (.venv reproducible desde uv.lock)"
        else
            log_warn "uv sync fallo — revisa pyproject.toml / uv.lock / red"
        fi
        return
    fi

    # Fallback legacy (sin pyproject.toml): crear venv + instalar requirements.
    if exists_dir "$venv_dir"; then
        log_info "Entorno virtual ya existe: ${venv_dir}"
    else
        log_info "Creando entorno virtual en ${venv_dir}..."
        if command_exists uv; then
            uv venv "$venv_dir" --quiet 2>&1 || python3 -m venv "$venv_dir"
        else
            python3 -m venv "$venv_dir"
        fi
        log_success "Entorno virtual creado"
    fi

    if exists_file "$requirements"; then
        log_info "Instalando dependencias desde ${requirements}..."
        if command_exists uv; then
            # uv pip install es ~10x mas rapido; idempotente.
            VIRTUAL_ENV="$venv_dir" uv pip install --quiet -r "$requirements" \
                || {
                    log_warn "  uv pip install fallo — cayendo a pip estandar"
                    "${venv_dir}/bin/pip" install --quiet --upgrade pip
                    "${venv_dir}/bin/pip" install --quiet -r "$requirements"
                }
        else
            "${venv_dir}/bin/pip" install --quiet --upgrade pip
            "${venv_dir}/bin/pip" install --quiet -r "$requirements"
        fi
        log_success "Dependencias instaladas"
    else
        log_warn "No se encontro: ${requirements}"
    fi
}

# -----------------------------------------------------------------------------
# _ensure_uv_installed
#   Instala uv (Astral) si no esta en PATH. Idempotente.
#   Sin sudo: usa installer oficial via curl que pone uv en ~/.local/bin.
#   D-031 / H-14: el equipo usa uv en todos los submodulos.
# -----------------------------------------------------------------------------
_ensure_uv_installed() {
    if command_exists uv; then
        return 0
    fi
    # uv puede estar instalado en ~/.local/bin sin estar en PATH
    if [[ -f "${HOME}/.local/bin/env" ]]; then
        # shellcheck disable=SC1091
        . "${HOME}/.local/bin/env" 2>/dev/null || true
        command_exists uv && return 0
    fi

    log_info "  Instalando uv (gestor de toolchain Python)..."
    if ! command_exists curl; then
        log_warn "  curl no disponible — saltando uv; setup_venv cae a pip"
        return 1
    fi

    # DEC-DOC-008: capturar stderr y propagar si falla.
    local install_log
    install_log=$(mktemp)
    if curl -LsSf https://astral.sh/uv/install.sh 2>"$install_log" \
            | sh > "$install_log" 2>&1; then
        [[ -f "${HOME}/.local/bin/env" ]] && \
            . "${HOME}/.local/bin/env" 2>/dev/null || true
        if command_exists uv; then
            log_success "  uv instalado: $(uv --version 2>/dev/null || echo 'OK')"
            rm -f "$install_log"
            return 0
        fi
    fi
    log_warn "  Instalacion de uv fallo:"
    sed 's/^/    /' "$install_log" >&2
    rm -f "$install_log"
    return 1
}
