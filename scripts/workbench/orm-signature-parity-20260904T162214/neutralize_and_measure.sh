#!/usr/bin/env bash
# El control que discrimina, sobre el arbol real y SIN escribir un archivo.
#
# Un comparador que devolviera siempre "no diverge" pasa todos los casos de
# TestTheComparison que exigen lista vacia, y los 20 en verde no distinguirian
# «las firmas coinciden» de «el instrumento no mira» — el sub-patron D de
# metrica-decide-la-conclusion.md.
#
# Aqui se le anula classify() en proceso y se mide QUE CAE y QUE SOBREVIVE.
# La neutralizacion es un parche de atributo en memoria: nada se escribe, asi
# que no hay archivo que restaurar (y no se roza la prohibicion de deshacer una
# edicion con git checkout, tarea #177).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../../.."
eval "$(python3 scripts/reference_roots.py --env)"

uv run python - "$HERE" <<'PY'
import pathlib
import sys

import pytest

HERE = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(HERE))
import signature_parity as sp                                  # noqa: E402

REF = pathlib.Path(sp.__file__)  # placeholder; la raiz real se arma abajo
import os                                                       # noqa: E402
raiz = pathlib.Path(os.environ['ODOO19C']) / 'odoo' / 'orm'
ref, mine = raiz / 'registry.py', pathlib.Path('src/orm/registry.py')

def marcados():
    return {d.symbol for d in sp.compare_file(ref, mine).divergences}

intacto = marcados()
print('== con classify() intacto ==')
print(f'  clear_all_caches marcado: {"clear_all_caches" in intacto}   (se exige True)')
print(f'  init_models      marcado: {"init_models" in intacto}   (se exige False)')

original = sp.classify
sp.classify = lambda ref_sig, mine_sig: None
anulado = marcados()
print()
print('== con classify() anulado a «nunca diverge» ==')
print(f'  clear_all_caches marcado: {"clear_all_caches" in anulado}   <- CAE: el control discrimina')
print(f'  init_models      marcado: {"init_models" in anulado}   <- sobrevive: mide otra cosa')
print(f'  divergencias del archivo: {len(intacto)} -> {len(anulado)}')

# Y la suite entera bajo la misma anulacion: cuantos casos caen.
class Anulador:
    def pytest_configure(self, config):
        sp.classify = lambda a, b: None

sp.classify = original
print()
print('== la suite bajo la misma anulacion ==')
codigo = pytest.main(['-q', '-p', 'no:randomly', '--no-header', '-x' if False else '--tb=no',
                      str(HERE / 'tests')], plugins=[Anulador()])
print(f'  exit de pytest: {codigo}   (se exige != 0: con el comparador anulado la suite DEBE caer)')
sys.exit(0 if codigo != 0 else 1)
PY
