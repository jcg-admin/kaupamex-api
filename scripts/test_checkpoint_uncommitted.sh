#!/usr/bin/env bash
# Suite de `checkpoint_uncommitted.sh`, con el episodio real como control.
#
# El guion nace de una perdida de trabajo, asi que su caso decisivo no es uno
# fabricado: es reproducir la perdida —`git checkout` sobre un archivo con
# trabajo sin commitear— y comprobar que el checkpoint la deshace.
#
# Corre sobre un repo sintetico en un directorio temporal propio: NO toca el
# arbol de kaupamex-api. Si tocara el arbol real, el guion que protege del
# borrado seria el que borra.
set -uo pipefail

GUION="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checkpoint_uncommitted.sh"
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

SANDBOX=$(mktemp -d)
trap 'rm -rf "$SANDBOX"' EXIT
cd "$SANDBOX"
git init -q .
git config user.email t@t; git config user.name t
echo "linea commiteada" > work.py
git add work.py
git commit -q -m "Seed"

# ── 1. Arbol limpio: no guarda, y lo dice ──────────────────────────────────
salida=$(bash "$GUION" clean-tree 2>&1)
check "arbol limpio lo declara" "si" \
      "$(echo "$salida" | grep -q 'SIN_CHECKPOINT' && echo si || echo no)"
check "arbol limpio no ancla ref" "0" \
      "$(git for-each-ref refs/checkpoints | wc -l)"

# ── 2. EL CONTROL: reproduce la perdida y la deshace ───────────────────────
# Es el episodio de L-025 verbatim: trabajo sin commitear, `git checkout`, y
# el trabajo desaparecido. Sin este caso la suite mediria que el guion crea
# un objeto, no que el objeto SIRVE para lo que existe.
echo "trabajo sin commitear" >> work.py
bash "$GUION" before-sabotage > /dev/null 2>&1
git checkout -- work.py                      # <- el comando que borro el trabajo
check "git checkout SI borra el trabajo (precondicion del caso)" "no" \
      "$(grep -q 'trabajo sin commitear' work.py && echo si || echo no)"
bash "$GUION" --restore before-sabotage work.py > /dev/null 2>&1
check "el checkpoint lo devuelve" "si" \
      "$(grep -q 'trabajo sin commitear' work.py && echo si || echo no)"

# ── 3. El arbol NO se toca al guardar ──────────────────────────────────────
# Es la diferencia con `git stash push`, que revierte lo que acabas de
# escribir. Si este caso cayera, el guion seria peor que no tenerlo.
echo "mas trabajo" >> work.py
antes=$(md5sum work.py | cut -d' ' -f1)
bash "$GUION" tree-untouched > /dev/null 2>&1
check "el arbol queda intacto tras guardar" "$antes" "$(md5sum work.py | cut -d' ' -f1)"

# ── 4. Un archivo sin seguir tambien entra ─────────────────────────────────
# `git stash create` no lo ve por si solo. Sin el `git add -A` previo, el
# checkpoint diria haber guardado y el archivo nuevo no estaria dentro.
echo "nacido en este pase" > brand_new.py
bash "$GUION" untracked-included > /dev/null 2>&1
check "el archivo sin seguir esta en el objeto" "si" \
      "$(git cat-file -e refs/checkpoints/untracked-included:brand_new.py 2>/dev/null \
         && echo si || echo no)"
check "y sigue en el arbol" "si" "$([ -f brand_new.py ] && echo si || echo no)"

# ── 5. El indice se restaura: guardar no deja nada en staging ──────────────
# El guion hace `git add -A` para ver los sin seguir. Si no deshiciera esa
# lectura del indice, el siguiente commit arrastraria archivos que nadie
# pidio — un efecto lateral silencioso.
check "nada queda en staging" "0" "$(git diff --cached --name-only | wc -l)"

# ── 6. Rehusa lo que no puede cumplir ──────────────────────────────────────
bash "$GUION" --restore no-existe work.py > /dev/null 2>&1
check "restaurar de un checkpoint inexistente sale 2" "2" "$?"
bash "$GUION" --restore before-sabotage no-existe.py > /dev/null 2>&1
check "restaurar un archivo ausente del objeto sale 2" "2" "$?"
bash "$GUION" "Slug Con Mayusculas" > /dev/null 2>&1
check "un slug fuera de kebab-case sale 2" "2" "$?"

# ── 7. Se puede listar lo guardado ─────────────────────────────────────────
check "el listado nombra los checkpoints" "si" \
      "$(bash "$GUION" --list | grep -q 'before-sabotage' && echo si || echo no)"

echo
echo "checkpoint_uncommitted: $PASSED aserciones OK, $FAILED fallidas"
[ "$FAILED" -eq 0 ] || exit 1
