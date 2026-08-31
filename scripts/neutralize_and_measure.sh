#!/usr/bin/env bash
# Anula una guarda, corre el subconjunto, y RESTAURA DESDE SU PROPIA COPIA.
#
# Es el control discriminante del sub-patron D de
# `metrica-decide-la-conclusion.md`: un test que sigue verde cuando la guarda
# desaparece no es una red, es un adorno. La unica forma de saberlo es quitar
# la guarda y comprobar que caen EXACTAMENTE los casos que dependen de ella.
#
# Por que existe como guion y no como tres comandos a mano
# =========================================================
#
# La restauracion se hacia con `git checkout <archivo>`, y eso **borra todo el
# trabajo sin commitear de ese archivo** — es la tarea #177, y ocurrio de
# verdad el 2026-08-30 sobre `src/orm/environments.py`: se perdieron la clase
# `Transaction` y la correccion de su docstring, y solo se recuperaron porque
# habia una copia previa por casualidad.
#
# Aqui la copia NO es casualidad: se hace antes de tocar nada y la
# restauracion sale de ella, nunca del indice de git. Si la copia no se pudo
# hacer, el guion rehusa en vez de neutralizar — un neutralizado sin vuelta
# atras no es una medicion, es una perdida.
#
# Uso:
#   bash scripts/neutralize_and_measure.sh <archivo> <sed-expr> <ruta-de-tests> <slug>
#
# Ejemplo:
#   bash scripts/neutralize_and_measure.sh src/orm/environments.py \
#       's/current\.clear()//' tests/unit/orm/test_environments_transaction.py \
#       scope-no-vacia
set -euo pipefail

ARCHIVO="${1:?falta el archivo a neutralizar}"
EXPRESION="${2:?falta la expresion sed que anula la guarda}"
TESTS="${3:?falta la ruta de tests}"
SLUG="${4:?falta el slug de la evidencia}"

[ -f "$ARCHIVO" ] || { echo "ERROR — no existe $ARCHIVO"; exit 2; }

# Segundo cinturon, anadido tras el episodio del 2026-08-31: la copia de abajo
# protege ESTE archivo, y el checkpoint protege TODO lo demas que este sin
# commitear cuando algo salga mal a mitad de la medicion. Cuesta un objeto de
# git y no toca el arbol.
bash "$(dirname "${BASH_SOURCE[0]}")/checkpoint_uncommitted.sh" \
    "before-neutering-${SLUG}" || echo "AVISO — el checkpoint fallo; la copia de abajo sigue en pie"

RESPALDOS=".neutering"
mkdir -p "$RESPALDOS"
COPIA="$RESPALDOS/$(echo "$ARCHIVO" | tr '/' '_').bak"

cp "$ARCHIVO" "$COPIA" || { echo "ERROR — no se pudo copiar; NO se neutraliza"; exit 2; }
# Rehusa si la copia salio vacia o distinta en tamano: restaurar de una copia
# rota es peor que no medir.
cmp -s "$ARCHIVO" "$COPIA" || { echo "ERROR — la copia no coincide; NO se neutraliza"; exit 2; }

EVIDENCIA="scripts/evidence/neutering-${SLUG}-$(date -u +%Y%m%dT%H%M%S).txt"

restaurar() {
    cp "$COPIA" "$ARCHIVO"
    if cmp -s "$ARCHIVO" "$COPIA"; then
        echo "restaurado desde $COPIA"
    else
        echo "ATENCION — la restauracion no coincide con la copia; revisar a mano"
    fi
}
trap restaurar EXIT

# El desenlace de una guarda anulada NO siempre es «N failed»: si la guarda
# sostenia el arranque, pytest ni siquiera colecciona y emite `error` o
# `INTERNALERROR`. Un filtro que solo viera `passed|failed|FAILED` publicaria
# una seccion VACIA, y una seccion vacia se lee como «no cayo nada» — el mismo
# verde-que-no-discrimina que este guion existe para atrapar. Medido: el porte
# de `base_field` como `property` aborta el arranque de Django entero, y la
# primera version de este filtro no lo vio.
SENALES='^([0-9]+ (passed|failed|error|errors|warning)|FAILED|ERROR |INTERNALERROR)'

medir() {
    local salida
    salida=$(uv run pytest "$TESTS" -q --reuse-db 2>&1 | grep -E "$SENALES" || true)
    if [ -z "$salida" ]; then
        # No emite vacio: un cero sin desenlace no es una medicion.
        echo "SIN DESENLACE RECONOCIDO — las diez ultimas lineas en crudo:"
        uv run pytest "$TESTS" -q --reuse-db 2>&1 | tail -10
    else
        echo "$salida"
    fi
}

{
    echo "# Control discriminante — $SLUG"
    echo "# fecha:    $(date -u +%Y-%m-%dT%H:%M:%S)"
    echo "# archivo:  $ARCHIVO"
    echo "# anulado:  $EXPRESION"
    echo "# tests:    $TESTS"
    echo
    echo "## 1. Verde de partida (guarda presente)"
    medir
    echo
    sed -i "$EXPRESION" "$ARCHIVO"
    echo "## 2. Con la guarda ANULADA — deben caer exactamente los casos que dependen de ella"
    medir
} | tee "$EVIDENCIA"

echo
echo "evidencia en $EVIDENCIA"
