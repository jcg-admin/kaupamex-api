"""Controles por neutralizacion de las dos guardas de tools/profiler.py.

Cada guarda se anula en el propio archivo, se corre la suite, se mide que cae,
y se restaura verificando la identidad del archivo por sha256 — nunca con
``git checkout``, que sobre un archivo sin seguir no restaura nada.
"""
import hashlib
import pathlib
import subprocess
import sys

FUENTE = pathlib.Path('src/tools/profiler.py')
SUITE = ['uv', 'run', 'pytest', 'tests/unit/tools/test_profiler.py', '-q', '--reuse-db']

GUARDAS = {
    'guarda del marco (PeriodicCollector.add)': (
        'if frame == self.last_frame:',
        'if False:  # GUARDA ANULADA — control',
    ),
    'salto de los marcos propios (get_current_frame)': (
        'while frame.f_code.co_filename == __file__:',
        'while False:  # GUARDA ANULADA — control',
    ),
}


def cola(texto, lineas=3):
    return '\n'.join(texto.strip().splitlines()[-lineas:])


def main():
    original = FUENTE.read_text()
    huella = hashlib.sha256(original.encode()).hexdigest()
    print(f'sha256 original: {huella}\n')

    base = subprocess.run(SUITE, capture_output=True, text=True)
    print('=== BASELINE, guardas puestas ===')
    print(cola(base.stdout), '\n')

    for nombre, (viejo, nuevo) in GUARDAS.items():
        if viejo not in original:
            sys.exit(f'ERROR — el literal de {nombre!r} no esta en el archivo')
        FUENTE.write_text(original.replace(viejo, nuevo, 1))
        try:
            anulada = subprocess.run(SUITE, capture_output=True, text=True)
            print(f'=== CONTROL — {nombre} anulada ===')
            print(cola(anulada.stdout, 12), '\n')
        finally:
            FUENTE.write_text(original)
        vuelta = hashlib.sha256(FUENTE.read_bytes()).hexdigest()
        print(f'restaurado: sha256 {"IGUAL" if vuelta == huella else "DISTINTO"} ({vuelta})\n')


if __name__ == '__main__':
    main()
