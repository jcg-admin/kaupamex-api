"""El par REAL contra el que se prueba el instrumento.

``TestTheControlCanFail`` no puede apoyarse en un caso fabricado: quien escribe
el patron lo escribiria a la medida de su propio encuadre, y el verde
resultante no distinguiria «el comparador funciona» de «el caso se escribio
para que pasara» (``hallazgo-abierto-genera-sucesor.md``).

Los dos anclajes salen de ``registry.py`` y estan verificados **leyendo la
fuente**, no aceptando el veredicto del instrumento — eso ultimo seria medir al
instrumento con su propia output:

- ``clear_all_caches`` DIVERGE. La referencia lo declara metodo de ``Registry``
  —``def clear_all_caches(self)``, ``odoo19c: odoo/orm/registry.py:988``— y aqui
  es funcion de modulo sin ``self`` (``src/orm/registry.py:303``).
- ``init_models`` COINCIDE. Los cinco positionals van en el mismo orden y
  ``install`` lleva default en ambos lados (``:723`` contra ``:2155``).

Si la referencia no esta montada, los dos casos del control se **saltan** en vez
de pasar: un verde sin referencia no distingue «coincide» de «no se midio», que
es el sub-patron D de ``metrica-decide-la-conclusion.md``.
"""
import os
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
API_ROOT = HERE.parents[3]          # scripts/workbench/<pieza>/tests → raiz de api

#: Los dos anclajes, con la line en que se leyeron.
DIVERGENT_ANCHOR = 'clear_all_caches'   # ref :988 (self) · aqui :303 ()
IDENTICAL_ANCHOR = 'init_models'        # ref :723 · aqui :2155 — mismos cinco


def _reference_root():
    """La raiz de ``odoo19c``, por el declarador unico de rutas del repo.

    Nunca se teclea la path larga: el arbol esta triplicado en ``odoo-tools`` y
    un literal aqui seria la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohibe.
    """
    base = os.environ.get('ODOO19C')
    if not base:
        try:
            output = subprocess.run(
                [sys.executable, str(API_ROOT / 'scripts' / 'reference_roots.py'), '--env'],
                capture_output=True, text=True, timeout=30, check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        for line in output.splitlines():
            if line.startswith("export ODOO19C="):
                base = line.split('=', 1)[1].strip().strip('"\'')
                break
    if not base:
        return None
    root = pathlib.Path(base) / 'odoo' / 'orm'
    return root if root.is_dir() else None


@pytest.fixture
def real_pair():
    """``(ref, mine, divergente, identico)`` — el par de archivos y sus anclajes."""
    root = _reference_root()
    if root is None:
        pytest.skip(
            'sin $ODOO19C no se puede medir el control: un verde aqui no '
            'distinguiria «las firmas coinciden» de «no habia referencia»'
        )
    ref = root / 'registry.py'
    mine = API_ROOT / 'src' / 'orm' / 'registry.py'
    for path in (ref, mine):
        if not path.is_file():
            pytest.skip(f'falta el archivo del control: {path}')
    return ref, mine, DIVERGENT_ANCHOR, IDENTICAL_ANCHOR
