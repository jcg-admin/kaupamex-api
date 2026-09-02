"""Control discriminante de #313 — cada guarda anulada, una a una.

No usa ``git checkout``: lee el texto, lo sustituye, corre el subconjunto y
restaura desde la copia en memoria (regla #177). Cierra comprobando el sha256
de cada archivo tocado.
"""
import hashlib
import pathlib
import subprocess
import sys

MODULO = 'tests/unit/orm/test_compute_writes_m2m.py'

GUARDAS = {
    'la rama del M2M en el volcado': (
        'src/orm/models.py',
        "            if getattr(field, 'many_to_many', False):\n"
        "                if row.pk in cached:\n"
        "                    _flush_m2m(row, field, cached[row.pk])\n"
        "                continue\n",
        "            if getattr(field, 'many_to_many', False):\n"
        "                continue  # GUARDA ANULADA\n",
    ),
    'el M2M dentro del predicado de persistido': (
        'src/orm/fields.py',
        "    return bool(getattr(field, 'store', False)\n"
        "                and (field.column_type\n"
        "                     or getattr(field, 'many_to_many', False)))\n",
        "    return bool(getattr(field, 'store', False)\n"
        "                and field.column_type)  # GUARDA ANULADA\n",
    ),
    'el guard de precompute sobre un M2M': (
        'src/orm/fields_nonstored.py',
        "        elif many_to_many:\n",
        "        elif False:  # GUARDA ANULADA\n",
    ),
}


def run():
    salida = subprocess.run(
        ['uv', 'run', 'pytest', MODULO, '-q', '--reuse-db',
         '-p', 'no:cacheprovider'],
        capture_output=True, text=True).stdout.strip().splitlines()
    return salida[-1] if salida else '(sin salida)'


print(f'linea base: {run()}')
for name, (ruta, old, new) in GUARDAS.items():
    archivo = pathlib.Path(ruta)
    original = archivo.read_text()
    firma = hashlib.sha256(original.encode()).hexdigest()
    if old not in original:
        sys.exit(f'ERROR — no se encontro la guarda «{name}» en {ruta}; '
                 f'el control no mide nada')
    archivo.write_text(original.replace(old, new, 1))
    try:
        print(f'sin {name}: {run()}')
    finally:
        archivo.write_text(original)
    if hashlib.sha256(archivo.read_text().encode()).hexdigest() != firma:
        sys.exit(f'ERROR — {ruta} no volvio a su estado original')
    print(f'   {ruta} restaurado (sha256 identico)')
