#!/bin/bash
# =============================================================================
# network.sh — Funciones de red — PracticaYoruba API
# =============================================================================
# Depende de: logging.sh
# =============================================================================

tcp_is_reachable() {
    local host="$1" port="$2" timeout="${3:-5}"

    if command -v nc &>/dev/null; then
        nc -z -w "$timeout" "$host" "$port" &>/dev/null
        return $?
    fi

    # Fallback bash built-in
    ( exec 3<>/dev/tcp/"$host"/"$port" ) &>/dev/null
    return $?
}

wait_for_port() {
    local host="$1" port="$2" attempts="${3:-10}" sleep_secs="${4:-2}"
    local i=0
    while (( i < attempts )); do
        tcp_is_reachable "$host" "$port" 2 && return 0
        i=$(( i + 1 ))
        log_info "Esperando ${host}:${port} ... intento ${i}/${attempts}"
        sleep "$sleep_secs"
    done
    log_error "Puerto ${host}:${port} no disponible despues de ${attempts} intentos"
    return 1
}
