#!/bin/bash
# =============================================================================
# database.sh — Funciones de base de datos — PracticaYoruba API
# =============================================================================
# MySQL / MariaDB. Una sola BD.
# Depende de: logging.sh, network.sh
# =============================================================================

mysql_is_running() {
    local host="${1:-127.0.0.1}" port="${2:-3306}"

    if command -v mysqladmin &>/dev/null; then
        mysqladmin ping --silent --host="$host" --port="$port" 2>/dev/null
        return $?
    fi

    tcp_is_reachable "$host" "$port" 3
}

mysql_start() {
    if mysql_is_running; then
        log_success "MySQL ya esta activo"
        return 0
    fi

    log_info "Arrancando MySQL..."

    if command -v service &>/dev/null; then
        service mysql start 2>/dev/null || service mariadb start 2>/dev/null || true
    fi

    sleep 3

    if mysql_is_running; then
        log_success "MySQL activo"
        return 0
    fi

    log_error "MySQL no responde despues del arranque"
    return 1
}
