#!/bin/bash
# =============================================================================
# core.sh — Funciones utilitarias core — PracticaYoruba API
# =============================================================================
# Depende de: logging.sh
# =============================================================================

command_exists() {
    command -v "$1" &>/dev/null
}

require_command() {
    local cmd="$1"
    if ! command_exists "$cmd"; then
        log_warn "Comando no encontrado: ${cmd}"
        return 1
    fi
    return 0
}

exists_file() { [[ -f "$1" ]]; }
exists_dir()  { [[ -d "$1" ]]; }
