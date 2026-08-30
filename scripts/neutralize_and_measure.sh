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

{
    echo "# Control discriminante — $SLUG"
    echo "# fecha:    $(date -u +%Y-%m-%dT%H:%M:%S)"
    echo "# archivo:  $ARCHIVO"
    echo "# anulado:  $EXPRESION"
    echo "# tests:    $TESTS"
    echo
    echo "## 1. Verde de partida (guarda presente)"
    uv run pytest "$TESTS" -q --reuse-db 2>&1 | grep -E '^([0-9]+ (passed|failed)|FAILED)' || true
    echo
    sed -i "$EXPRESION" "$ARCHIVO"
    echo "## 2. Con la guarda ANULADA — deben caer exactamente los casos que dependen de ella"
    uv run pytest "$TESTS" -q --reuse-db 2>&1 | grep -E '^([0-9]+ (passed|failed)|FAILED)' || true
} | tee "$EVIDENCIA"

echo
echo "evidencia en $EVIDENCIA"
