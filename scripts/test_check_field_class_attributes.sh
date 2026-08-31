#!/usr/bin/env bash
# Suite de `check_field_class_attributes.py` — el gate de la tarea #246.
#
# Los dos casos que importan son SABOTAJES, no verdes: un gate que no falla
# cuando el defecto vuelve no es un gate. Y no son hipoteticos — los dos
# destaparon un defecto REAL del propio gate mientras se escribia:
#
#   control 1 (Id)      -> el gate solo miraba SOBRESCRITURAS, y la divergencia
#                          de la clave primaria es que la fuente HEREDA el
#                          defecto de Field donde Django hereda el del entero.
#                          Publicaba 0 nuevos con el defecto puesto.
#   control 2 (Integer) -> `agrees` comparaba por veracidad, asi que None
#                          pasaba por 0. Colapsaba justo la distincion que
#                          falsy_value codifica.
#
# El sabotaje se aplica y se restaura DESDE UN CHECKPOINT, nunca con
# `git checkout`: es la tarea #177 y L-025.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
GATE="uv run python scripts/check_field_class_attributes.py"
TARGET="src/orm/fields.py"
SLUG="test-field-class-attributes-$$"
PASSED=0
FAILED=0

check() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
        echo "FALLO — $label"
        echo "   esperado: $expected"
        echo "   obtenido: $actual"
    fi
}

bash scripts/checkpoint_uncommitted.sh "$SLUG" > /dev/null 2>&1
restore() {
    bash scripts/checkpoint_uncommitted.sh --restore "$SLUG" "$TARGET" > /dev/null 2>&1 \
        || git show "HEAD:$TARGET" > "$TARGET"
}
trap restore EXIT

# ── 1. Verde de partida ────────────────────────────────────────────────────
$GATE --strict > /dev/null 2>&1
check "el arbol limpio pasa" "0" "$?"

# ── 2. Publica su denominador ──────────────────────────────────────────────
# Sin el, un 0 incumplidores no se distingue de 0 medidos (H-API-335).
salida=$($GATE 2>&1)
check "publica el alcance medido" "si" \
      "$(echo "$salida" | grep -q 'alcance medido: [0-9]\+ pares' && echo si || echo no)"
check "publica la exclusion estructural" "si" \
      "$(echo "$salida" | grep -q 'fuera del alcance por construccion' && echo si || echo no)"

# ── 3. CONTROL 1 — la segunda forma: heredar el defecto de la base ─────────
sed -i "s/^    'Id': None,$/    # 'Id': None,/" "$TARGET"
salida=$($GATE --strict 2>&1); estado=$?
check "retirar Id sale 1" "1" "$estado"
check "y nombra las TRES clases de clave primaria" "3" \
      "$(echo "$salida" | grep -c '^  falsy_value ')"
check "citando el valor vivo, no solo el esperado" "si" \
      "$(echo "$salida" | grep -q 'aqui: 0' && echo si || echo no)"
restore

# ── 4. CONTROL 2 — la primera forma: la sobrescritura por clase ────────────
sed -i "s/^    'Integer': 0,$/    # 'Integer': 0,/" "$TARGET"
salida=$($GATE --strict 2>&1); estado=$?
check "retirar Integer sale 1" "1" "$estado"
check "y nombra IntegerField" "si" \
      "$(echo "$salida" | grep -q 'falsy_value.*IntegerField' && echo si || echo no)"
check "None NO pasa por 0" "si" \
      "$(echo "$salida" | grep -q 'aqui: None' && echo si || echo no)"
restore

# ── 5. La restauracion devolvio el archivo ────────────────────────────────
# Sin este caso, un `restore` roto dejaria los sabotajes puestos y el resto de
# la suite mediria un arbol saboteado creyendolo limpio.
$GATE --strict > /dev/null 2>&1
check "vuelve a pasar tras restaurar" "0" "$?"
check "sin sabotajes en el archivo" "0" \
      "$(grep -c "^    # 'Id': None,\|^    # 'Integer': 0," "$TARGET")"

# ── 6. Rehusa sin conteo cuando no puede medir ────────────────────────────
# Un 0 sin poder arrancar Django seria el verde falso que el gate atrapa.
salida=$(python3 scripts/check_field_class_attributes.py 2>&1 || true)
check "con el interprete del sistema rehusa" "si" \
      "$(echo "$salida" | grep -q 'interprete del proyecto' && echo si || echo no)"
check "y NO emite conteo" "no" \
      "$(echo "$salida" | grep -q 'alcance medido' && echo si || echo no)"

echo
echo "check_field_class_attributes: $PASSED aserciones OK, $FAILED fallidas"
[ "$FAILED" -eq 0 ] || exit 1
