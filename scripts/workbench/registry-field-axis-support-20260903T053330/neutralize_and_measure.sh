#!/usr/bin/env bash
# El control que discrimina, sobre el arbol real y sin tocar un archivo.
#
# Un clasificador que dijera BUILDABLE sin resolver nada pasaria los ocho
# simbolos, y el verde no distinguiria «las primitivas estan» de «el
# instrumento no las mira». Aqui se le retira a src/ del PYTHONPATH: las
# primitivas de tools.misc y de orm.* dejan de resolver, y el clasificador
# tiene que decir BLOCKED en los seis simbolos que las piden.
#
# Nada se escribe: la neutralizacion es de entorno, asi que no hay que
# restaurar ningun archivo.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../../.."

echo "== con src/ en la ruta: el estado normal =="
DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
    uv run python -c "
import django; django.setup()
import runpy, sys
sys.argv = ['classify', '--json']
runpy.run_path('$HERE/classify_field_axis_support.py', run_name='__main__')
" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('  BLOCKED:', len(d['buckets']['BLOCKED']), 'de', d['total'])
sys.exit(0 if not d['buckets']['BLOCKED'] else 1)
"

echo
echo "== sin src/ en la ruta: las primitivas propias no resuelven =="
DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH= \
    uv run python -c "
import runpy, sys
sys.argv = ['classify', '--json']
runpy.run_path('$HERE/classify_field_axis_support.py', run_name='__main__')
" | python3 -c "
import json, sys
d = json.load(sys.stdin)
bloqueados = d['buckets']['BLOCKED']
print('  BLOCKED:', len(bloqueados), 'de', d['total'], '->', ', '.join(bloqueados))
for nombre, ausentes in sorted(d['missing'].items()):
    print('   ', nombre, 'AUSENTE:', ', '.join(ausentes))
if not bloqueados:
    print('  FALLO DEL CONTROL: el clasificador no sabe decir que no')
    sys.exit(1)
"

echo
echo "El control discrimina: el mismo guion responde distinto cuando las"
echo "primitivas dejan de estar. Un verde suyo mide el arbol, no su propia forma."
