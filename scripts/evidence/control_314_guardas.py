"""Control discriminante de #314 — cada guarda anulada, una a una.

No usa ``git checkout``: lee el texto, lo sustituye, corre el subconjunto y
restaura desde la copia en memoria (regla #177). Al final verifica que el
arbol quedo intacto con ``git diff --stat``.
"""
import pathlib
import subprocess
import sys

ARCHIVO = pathlib.Path('src/addons/base/models/res_partner.py')
MODULO = 'tests/unit/base/test_commercial_partner_field.py'

GUARDAS = {
    'el propagador al guardar': (
        "        self._store_commercial_entity()",
        "        pass  # GUARDA ANULADA",
    ),
    'la subida recursiva por el padre': (
        "        self.commercial_partner_id = (\n"
        "            self.parent.commercial_partner_id or self.parent)",
        "        self.commercial_partner_id = self.parent  # GUARDA ANULADA",
    ),
}


def run():
    return subprocess.run(
        ['uv', 'run', 'pytest', MODULO, '-q', '--reuse-db',
         '-p', 'no:cacheprovider'],
        capture_output=True, text=True).stdout.strip().splitlines()[-1]


original = ARCHIVO.read_text()
print(f'linea base: {run()}')
for name, (old, new) in GUARDAS.items():
    if old not in original:
        sys.exit(f'ERROR — no se encontro la guarda «{name}»; el control no mide nada')
    ARCHIVO.write_text(original.replace(old, new, 1))
    try:
        print(f'sin {name}: {run()}')
    finally:
        ARCHIVO.write_text(original)

diff = subprocess.run(['git', 'diff', '--stat', '--', str(ARCHIVO)],
                      capture_output=True, text=True).stdout.strip()
print(f'arbol restaurado: {diff or "(sin cambios)"}')
