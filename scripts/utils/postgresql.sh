#!/bin/bash
# =============================================================================
# utils/postgresql.sh — helpers de PostgreSQL para el bootstrap de api
# =============================================================================
#
# Deliberadamente **delgado**. El motor lo provisiona el submódulo ``db``, que
# ya trae ``scripts/start_postgres.sh``, ``provisioners/postgresql/db_setup.sh``
# y ``utils/postgresql.sh`` con ocho helpers. Duplicarlos aquí reintroduciría
# el defecto que ``provisioners/mysql/`` produjo: dos copias del mismo
# provisioning que envejecen por separado.
#
# Aquí sólo vive lo que api necesita para **decidir si puede seguir**:
# localizar el submódulo hermano y preguntar si el servidor responde.
#
# Nombre explícito, no genérico — mismo criterio que ``db: utils/postgresql.sh``
# junto a ``utils/database.sh``: el archivo dice a qué motor sirve.
# =============================================================================

# Localiza el clon hermano de kaupamex-db. Imprime la ruta y devuelve 0; si no
# lo encuentra, no imprime nada y devuelve 1.
#
# Dos nombres, no tres. ``kaupamex-db`` es el clon hermano (el remote real es
# ``jcg-admin/kaupamex-db``); ``db`` es la ruta del submódulo cuando se trabaja
# desde el superproyecto. ``Kaupamex-db`` NO se acepta: es un nombre de
# repositorio muerto desde el rename del 2026-07-23 (DEC-KX-06) y aceptarlo
# arrastra branding retirado en el mismo pase que lo elimina.
db_repo_root() {
    local parent
    parent="$(cd "${PROJECT_ROOT}/.." && pwd)" || return 1
    local cand
    for cand in "${parent}/kaupamex-db" "${parent}/db"; do
        if [[ -d "$cand" && -f "${cand}/provisioners/postgresql/db_setup.sh" ]]; then
            printf '%s\n' "$cand"
            return 0
        fi
    done
    return 1
}

# ¿Responde el servidor? ``pg_isready`` es el gate canónico del proyecto
# (test-execution-protocol.md) y viene en postgresql-client.
#
# NO se implementa un fallback "a mano" con psql: un fallo de autenticación y
# uno de servidor caído se ven distintos en pg_isready y ese matiz es el que
# H-DB-05 costó descubrir.
postgres_is_running() {
    command -v pg_isready >/dev/null 2>&1 || return 1
    pg_isready >/dev/null 2>&1
}
