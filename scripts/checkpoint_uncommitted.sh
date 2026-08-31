#!/usr/bin/env bash
# Guarda el trabajo sin commitear como un COMMIT REAL, sin tocar el arbol.
#
# Por que existe
# ==============
#
# `git checkout <archivo>` no deshace la ultima edicion: sustituye el archivo
# por su version de HEAD. Sobre un archivo con trabajo sin commitear borra el
# trabajo legitimo junto con lo que se queria deshacer, sin confirmacion y sin
# reflog que lo recupere. Es la tarea #177, y ya ocurrio dos veces:
#
#   2026-08-30  src/orm/environments.py  — se perdieron la clase Transaction y
#               la correccion de su docstring (L-024). De ese episodio nacio
#               `neutralize_and_measure.sh`, que hace la copia por ti.
#   2026-08-31  src/orm/registry.py      — se perdieron `not_null_fields` e
#               `is_not_null`, escritas en el mismo pase (L-025). El guion de
#               arriba EXISTIA y no se uso: el sabotaje se hizo a mano.
#
# La leccion del segundo episodio no es «hace falta un guion» — ya lo habia.
# Es que la proteccion tiene que valer **tambien cuando la operacion se hace a
# mano**, porque a mano es como se hace la mitad de las veces.
#
# Que hace, y por que asi
# =======================
#
# `git stash create` construye un objeto commit con el estado del arbol y **no
# toca el arbol ni el indice**: no hay que acordarse de deshacer nada despues.
# Ese objeto nace colgando de nada, asi que el recolector de basura se lo
# lleva; `git update-ref` lo ancla bajo `refs/checkpoints/<slug>` y con eso
# sobrevive.
#
# Frente a las dos alternativas obvias:
#
#   - un commit en la rama       -> ensucia el historial con WIP que luego hay
#                                   que aplastar, y cambia HEAD.
#   - `git stash push`           -> SI toca el arbol: revierte lo que acabas de
#                                   escribir, que es justo lo que no queremos.
#
# Uso
# ===
#
#   bash scripts/checkpoint_uncommitted.sh <slug>          # guarda
#   bash scripts/checkpoint_uncommitted.sh --list          # que hay guardado
#   bash scripts/checkpoint_uncommitted.sh --show <slug>   # los archivos
#   bash scripts/checkpoint_uncommitted.sh --restore <slug> <archivo>
#
# La recuperacion de un archivo suelto no necesita el guion:
#
#   git show refs/checkpoints/<slug>:<archivo> > <archivo>
set -euo pipefail

readonly REF_PREFIX='refs/checkpoints'

fail() { echo "ERROR — $*" >&2; exit 2; }

list_checkpoints() {
    local found
    found=$(git for-each-ref --format='%(refname:short)  %(objectname:short)  %(subject)' \
        "$REF_PREFIX" || true)
    if [ -z "$found" ]; then
        echo "sin checkpoints guardados"
    else
        echo "$found"
    fi
}

case "${1:-}" in
    --list)
        list_checkpoints
        exit 0
        ;;
    --show)
        slug="${2:?falta el slug}"
        git rev-parse --verify "$REF_PREFIX/$slug" >/dev/null 2>&1 \
            || fail "no existe el checkpoint '$slug'"
        git show --stat --format='%H%n%s%n' "$REF_PREFIX/$slug"
        exit 0
        ;;
    --restore)
        slug="${2:?falta el slug}"
        target="${3:?falta el archivo a restaurar}"
        git rev-parse --verify "$REF_PREFIX/$slug" >/dev/null 2>&1 \
            || fail "no existe el checkpoint '$slug'"
        git cat-file -e "$REF_PREFIX/$slug:$target" 2>/dev/null \
            || fail "el checkpoint '$slug' no contiene $target"
        # La restauracion sale del objeto, NUNCA del indice: por eso este
        # guion existe.
        git show "$REF_PREFIX/$slug:$target" > "$target"
        echo "restaurado $target desde $REF_PREFIX/$slug"
        exit 0
        ;;
esac

slug="${1:?falta el slug del checkpoint (ej: antes-de-sabotear-is-not-null)}"
[[ "$slug" =~ ^[a-z0-9][a-z0-9-]*$ ]] \
    || fail "el slug va en kebab-case minuscula: '$slug'"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "no es un repo git"

pending=$(git status --porcelain --untracked-files=all)
if [ -z "$pending" ]; then
    # No es un fallo: no hay nada que perder, asi que no hay nada que guardar.
    # Se dice en voz alta para que el que llama no crea que guardo algo.
    echo "arbol limpio — no hay trabajo sin commitear que guardar"
    echo "SIN_CHECKPOINT"
    exit 0
fi

# `stash create` no ve los archivos sin seguir. Se anaden al indice para que
# entren en el objeto; el arbol no se toca y el indice se restaura despues.
index_before=$(git write-tree)
git add -A
sha=$(git stash create "checkpoint: $slug") || fail "git stash create fallo"
git read-tree "$index_before"

[ -n "$sha" ] || fail "git stash create no devolvio objeto; NO hay checkpoint"

git update-ref "$REF_PREFIX/$slug" "$sha" \
    || fail "no se pudo anclar el objeto; el recolector se lo llevaria"

# El objeto tiene que contener lo que se acaba de guardar, o el checkpoint
# miente. Se verifica leyendolo de vuelta, no asumiendolo.
saved=$(git show --stat --format='' "$REF_PREFIX/$slug" | tail -1)
echo "checkpoint $REF_PREFIX/$slug -> $(git rev-parse --short "$sha")"
echo "  $saved"
echo "  recuperar un archivo:  git show $REF_PREFIX/$slug:<archivo> > <archivo>"
