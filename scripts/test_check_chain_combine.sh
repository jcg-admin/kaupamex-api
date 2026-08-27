#!/usr/bin/env bash
# Suite del gate scripts/check_chain_combine.py.
#
# El control positivo NO es un incumplidor fabricado: es el defecto real de
# H-API-823 —el combine= de addons/web/models/res_users_settings.py— retirado y
# restaurado. Un gate probado solo contra un caso escrito por quien escribio el
# patron hereda su encuadre y confirma el instrumento en vez de medirlo.
set -uo pipefail
cd "$(dirname "$0")/.."

GATE=scripts/check_chain_combine.py
VICTIMA=addons/web/models/res_users_settings.py
COPIA=$(mktemp)
ok=0; fallo=0

comprueba() {  # nombre, esperado, obtenido
    if [[ "$2" == "$3" ]]; then ok=$((ok+1))
    else fallo=$((fallo+1)); echo "  FAIL $1: esperaba '$2', obtuvo '$3'"; fi
}

# 1. El arbol tal cual pasa: la deuda revisada esta en baseline.
python3 "$GATE" --strict --quiet >/dev/null 2>&1
comprueba "arbol limpio sale 0" 0 $?

# 2. El denominador se publica — un cero sin alcance no discrimina entre
#    "no falta nada" y "no se midio" (sub-patron D).
salida=$(python3 "$GATE")
comprueba "publica el alcance" 1 "$(grep -c 'alcance medido' <<<"$salida")"

# 3. Control positivo: retirar el combine= real reintroduce H-API-823.
cp "$VICTIMA" "$COPIA"
python3 - <<'PY'
import pathlib
p = pathlib.Path('addons/web/models/res_users_settings.py')
t = p.read_text()
p.write_text(t.replace(
    "        ResUsersSettings, '_format_settings', _format_settings,\n"
    "        combine=merge_dict)",
    "        ResUsersSettings, '_format_settings', _format_settings)"))
PY
salida=$(python3 "$GATE" --strict); codigo=$?
comprueba "sin el combine sale 1" 1 $codigo
comprueba "y nombra al ofensor" 1 "$(grep -c 'res_users_settings.py' <<<"$salida")"
cp "$COPIA" "$VICTIMA"; rm -f "$COPIA"
comprueba "restaura el arbol" "" "$(git diff --name-only -- "$VICTIMA")"

# 4. El baseline absuelve, no borra: cada entrada sigue en el conteo.
comprueba "el baseline se publica" 1 \
    "$(python3 "$GATE" | grep -c '8 en baseline')"

# 5. Sin arbol de referencia el gate NO emite un cero: lo dice y se abstiene.
salida=$(ODOO19C=/no/existe python3 "$GATE" --strict); codigo=$?
comprueba "sin referencia sale 0 avisando" 0 $codigo
comprueba "y lo declara" 1 "$(grep -c 'no esta el arbol de referencia' <<<"$salida")"

echo "test-check-chain-combine: $ok asercion(es) OK, $fallo fallo(s)"
exit $(( fallo > 0 ))
