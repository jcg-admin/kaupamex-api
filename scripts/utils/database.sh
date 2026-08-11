#!/bin/bash
# =============================================================================
# RETIRADO — motor MariaDB (ADR-028, 2026-08-06). NO sirve a ningún entorno.
# =============================================================================
# `bootstrap.sh` dejó de invocarlo: la Fase 4 delega el provisioning en
# `kaupamex-db` (`provisioners/postgresql/db_setup.sh [--qa]`), que es donde
# vive el motor en uso. Este archivo sigue en el repo porque lo citan docs,
# el runbook E2E de `ui`, `db/scripts/sync-and-test.sh` y ADR-004 — no porque
# algo lo ejecute. Retirarlo exige limpiar antes esas citas: sucesor
# registrado en H-API-385. No editar para "actualizarlo": el motor cambió.
# =============================================================================
# =============================================================================
# database.sh — Funciones de base de datos — PracticaYoruba API
# =============================================================================
# MySQL / MariaDB.
# Depende de: logging.sh, network.sh
#
# D-031 / H-17 (mismo patron que D-028 del submodulo db): en MariaDB
# 11.x el CLI canonico es 'mariadb' y la herramienta admin es
# 'mariadb-admin'. Los aliases legacy 'mysql' / 'mysqladmin' ya NO se
# instalan en Ubuntu 24.04 noble con mariadb-client. Los helpers
# mariadb_client_bin / mariadb_admin_bin resuelven el binario
# disponible. Variables exportadas MARIADB_CLI / MARIADB_ADM al
# sourcear este archivo.
#
# Funciones publicas:
#   mariadb_client_bin    — devuelve binario CLI disponible (mariadb|mysql)
#   mariadb_admin_bin     — devuelve binario admin (mariadb-admin|mysqladmin)
#   mysql_is_running      — detecta si el servidor responde (TCP o socket)
#   mysql_cleanup_stale   — limpia archivos pid/sock de sesiones anteriores
#   mysql_start           — arranca MySQL/MariaDB (systemd o directo)
#   mysql_wait_ready      — espera activa hasta que el servidor responda
# =============================================================================

# Rutas de socket conocidas de MySQL/MariaDB en Ubuntu
_MYSQL_SOCKETS=(
    "/run/mysqld/mysqld.sock"
    "/var/run/mysqld/mysqld.sock"
    "/tmp/mysql.sock"
)

# Archivo PID primario que usa el proyecto
_MYSQL_PID_FILE="/run/mysqld/mysqld.pid"

# -----------------------------------------------------------------------------
# mariadb_client_bin / mariadb_admin_bin (D-028 / D-031 H-17)
#   Resuelven el binario disponible. Preferencia: canonico (mariadb /
#   mariadb-admin) sobre legacy (mysql / mysqladmin). Cadena vacia si
#   ninguno esta instalado.
# -----------------------------------------------------------------------------
mariadb_client_bin() {
    if command -v mariadb &>/dev/null; then echo "mariadb"
    elif command -v mysql &>/dev/null; then echo "mysql"
    else echo ""; fi
}

mariadb_admin_bin() {
    if command -v mariadb-admin &>/dev/null; then echo "mariadb-admin"
    elif command -v mysqladmin &>/dev/null; then echo "mysqladmin"
    else echo ""; fi
}

# Resolucion al sourcear. Re-resolver tras instalacion de mariadb-client
# con: MARIADB_CLI=$(mariadb_client_bin); MARIADB_ADM=$(mariadb_admin_bin).
MARIADB_CLI="$(mariadb_client_bin)"
MARIADB_ADM="$(mariadb_admin_bin)"
export MARIADB_CLI MARIADB_ADM

# -----------------------------------------------------------------------------
# mysql_is_running [host] [port]
#   Retorna 0 si el servidor responde, 1 si no.
#   Verifica en este orden:
#     1. Unix socket (rapido, funciona en contenedores sin red)
#     2. TCP (host:port)
# -----------------------------------------------------------------------------
mysql_is_running() {
    local host="${1:-127.0.0.1}" port="${2:-3306}"

    # 1. Intentar via socket Unix
    if [[ -n "${MARIADB_ADM:-}" ]]; then
        for sock in "${_MYSQL_SOCKETS[@]}"; do
            if [[ -S "$sock" ]]; then
                if "${MARIADB_ADM:-mariadb-admin}" --socket="$sock" ping --silent >/dev/null 2>&1; then
                    return 0
                fi
            fi
        done
    fi

    # 2. Intentar via TCP
    if [[ -n "${MARIADB_ADM:-}" ]]; then
        if "${MARIADB_ADM:-mariadb-admin}" ping --silent --host="$host" --port="$port" >/dev/null 2>&1; then
            return 0
        fi
    fi

    # 3. Fallback: solo verificar conectividad TCP (sin autenticacion)
    tcp_is_reachable "$host" "$port" 3
}

# -----------------------------------------------------------------------------
# mysql_cleanup_stale
#   Detecta y elimina archivos .pid y .sock que apuntan a procesos muertos.
#   Esto ocurre cuando el contenedor se reinicia sin apagar MySQL limpiamente.
#   Solo elimina archivos cuyo PID ya no existe en /proc.
# -----------------------------------------------------------------------------
mysql_cleanup_stale() {
    local cleaned=0

    # Limpiar PID files de procesos muertos
    for pid_file in /run/mysqld/*.pid; do
        [[ -f "$pid_file" ]] || continue
        local pid
        pid=$(cat "$pid_file" 2>/dev/null) || continue
        if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
            log_warn "PID stale detectado: ${pid_file} (PID ${pid} no existe)"
            rm -f "$pid_file"
            cleaned=$(( cleaned + 1 ))
        fi
    done

    # Limpiar socket files sin proceso activo
    for sock in "${_MYSQL_SOCKETS[@]}"; do
        [[ -S "$sock" ]] || continue
        # Intentar conectar — si falla con ECONNREFUSED el proceso no existe
        if ! "${MARIADB_ADM:-mariadb-admin}" --socket="$sock" ping --silent >/dev/null 2>&1; then
            log_warn "Socket stale detectado: ${sock}"
            rm -f "$sock"
            cleaned=$(( cleaned + 1 ))
        fi
    done

    (( cleaned > 0 )) && log_info "Limpiados ${cleaned} archivos stale" || true
}

# -----------------------------------------------------------------------------
# _mysql_start_systemd
#   Intenta arrancar MySQL via service/systemctl.
#   Retorna 0 si tuvo exito, 1 si el gestor no esta disponible o fallo.
# -----------------------------------------------------------------------------
_mysql_start_systemd() {
    command -v service &>/dev/null || return 1

    service mysql   start 2>/dev/null && return 0
    service mariadb start 2>/dev/null && return 0

    return 1
}

# -----------------------------------------------------------------------------
# _mysql_start_direct
#   Arranca mariadbd/mysqld directamente con nohup.
#   Usado como fallback en contenedores sin systemd.
#   Busca el binario en rutas conocidas de Ubuntu 24.04.
# -----------------------------------------------------------------------------
_mysql_start_direct() {
    local daemon=""
    for bin in /usr/sbin/mariadbd /usr/sbin/mysqld /usr/bin/mariadbd; do
        [[ -x "$bin" ]] && daemon="$bin" && break
    done

    if [[ -z "$daemon" ]]; then
        log_error "No se encontro el daemon de MariaDB/MySQL en rutas conocidas"
        return 1
    fi

    log_info "Arrancando ${daemon} directamente (sin systemd)..."

    nohup su -s /bin/bash mysql -c \
        "${daemon} \
         --datadir=/var/lib/mysql \
         --socket=/run/mysqld/mysqld.sock \
         --pid-file=${_MYSQL_PID_FILE} \
         --log-error=/var/lib/mysql/mysqld_err.log \
         --bind-address=127.0.0.1 \
         --port=3306" \
        > /tmp/mysqld_startup.log 2>&1 &

    return 0
}

# -----------------------------------------------------------------------------
# mysql_wait_ready [timeout_secs]
#   Espera activamente hasta que mysql_is_running retorne 0.
#   Retorna 0 si el servidor respondio antes del timeout, 1 si no.
# -----------------------------------------------------------------------------
mysql_wait_ready() {
    local timeout="${1:-30}" elapsed=0 interval=2

    log_info "Esperando a que MySQL este listo (timeout: ${timeout}s)..."

    while (( elapsed < timeout )); do
        if mysql_is_running; then
            log_success "MySQL listo (${elapsed}s)"
            return 0
        fi
        sleep "$interval"
        elapsed=$(( elapsed + interval ))
        log_info "  ... ${elapsed}s / ${timeout}s"
    done

    log_error "MySQL no respondio en ${timeout}s"
    log_error "Revisa el log: /var/lib/mysql/mysqld_err.log"
    return 1
}

# -----------------------------------------------------------------------------
# mysql_start
#   Punto de entrada principal.
#   Flujo:
#     1. Si ya corre -> retornar 0 inmediatamente
#     2. Limpiar estado stale de sesiones anteriores
#     3. Intentar arranque via systemd/service
#     4. Si falla, intentar arranque directo (contenedores)
#     5. Esperar activamente hasta que responda
# -----------------------------------------------------------------------------
mysql_start() {
    # 1. Ya esta corriendo
    if mysql_is_running; then
        log_success "MySQL ya esta activo"
        return 0
    fi

    log_info "MySQL no responde. Iniciando procedimiento de arranque..."

    # 2. Limpiar estado stale
    mysql_cleanup_stale

    # 3. Intentar via systemd/service
    if _mysql_start_systemd; then
        log_info "Arranque via service solicitado"
    else
        log_info "service no disponible — intentando arranque directo"
        _mysql_start_direct || {
            log_error "No se pudo iniciar MySQL"
            return 1
        }
    fi

    # 4. Esperar a que responda (30s maximo)
    mysql_wait_ready 30
}
