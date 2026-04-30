#!/bin/bash
# =============================================================================
# database.sh — Funciones de base de datos — PracticaYoruba API
# =============================================================================
# Solo PostgreSQL. TiendaMax usa una unica BD (sin DB legacy).
# Depende de: logging.sh, network.sh
# =============================================================================

pg_is_running() {
    local host="${1:-127.0.0.1}" port="${2:-5432}"

    if command -v pg_isready &>/dev/null; then
        pg_isready -h "$host" -p "$port" -q 2>/dev/null
        return $?
    fi

    tcp_is_reachable "$host" "$port" 3
}

pg_start() {
    local version="${1:-16}" cluster="${2:-main}"

    if pg_is_running; then
        log_success "PostgreSQL ya esta activo"
        return 0
    fi

    log_info "Arrancando PostgreSQL..."

    if command -v pg_ctlcluster &>/dev/null; then
        pg_ctlcluster "$version" "$cluster" start 2>&1 | tail -3 || true
    elif command -v service &>/dev/null; then
        service postgresql start 2>/dev/null || true
    else
        log_warn "No se encontro pg_ctlcluster ni service"
        return 1
    fi

    sleep 2

    if pg_is_running; then
        log_success "PostgreSQL activo"
        return 0
    fi

    log_error "PostgreSQL no responde despues del arranque"
    return 1
}
