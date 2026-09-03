#!/usr/bin/env bash
# Control por neutralizacion: retira ``src`` del PYTHONPATH y vuelve a medir.
#
# Sin el, el reparto READY/BUILDABLE/BLOCKED no discrimina: un clasificador que
# devolviera BUILDABLE siempre daria la misma salida. Con la raiz neutralizada,
# los simbolos que se apoyan en NUESTRO arbol —``tools.sql.SQL``,
# ``orm.registry._CACHES_BY_KEY``, ``orm.registry.Registry.new``— pasan a
# BLOCKED y el instrumento los nombra.
#
# La medicion del dia queda en outputs/. La del control tambien: la diferencia
# entre las dos ES el resultado.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
CLASSIFIER="$HERE/classify_signaling_axis_support.py"
STAMP="$(date -u +%Y%m%dT%H%M%S)"

echo "== con el arbol en PYTHONPATH =="
cd "$ROOT"
DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH="$ROOT/src" \
    "$ROOT/.venv/bin/python" "$CLASSIFIER" | tee "$HERE/outputs/con-arbol-$STAMP.txt"

echo
echo "== con el arbol NEUTRALIZADO (sin src en PYTHONPATH) =="
cd /
DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH= \
    "$ROOT/.venv/bin/python" "$CLASSIFIER" \
    | tee "$HERE/outputs/sin-arbol-$STAMP.txt"
