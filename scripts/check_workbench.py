#!/usr/bin/env python3
"""Gate del banco de trabajo — un trabajo declara donde aterriza lo que produce.

Verifica que cada directorio de ``scripts/workbench/`` lleve su
``manifest.json`` con las cinco claves que ``manifest_schema.json`` declara
obligatorias: ``question``, ``instrument``, ``metric``, ``blind_to`` y
``destination``.

Por que ESAS cinco
==================

No son ceremonia. Cada una cierra un defecto que este proyecto ya midio:

- ``question`` — un trabajo sin pregunta produce una salida que nadie sabe
  leer. Es la mitad que ``auto-audit-before-writing.md`` llama premisa.
- ``instrument`` — sin el, la cifra no se puede re-derivar y la unica forma
  de corregirla es reescribirla a mano.
- ``metric`` y ``blind_to`` — son ``metrica-decide-la-conclusion.md`` hecho
  campo obligatorio. Una cifra correcta sobre lo que no se pregunta engana
  igual que una equivocada, y el sub-patron C reincidio tres veces en la
  iniciativa de porte.
- ``destination`` — se declara ANTES de que exista lo que produce. Un trabajo
  sin destino declarado aterriza donde caiga, y ahi no lo encuentra nadie.

Nace SIN baseline
=================

Directiva del ejecutor 2026-08-30: *«ya no queremos deuda congelada»*. Un
baseline suprime hallazgos reales para que el gate no bloquee, y es la forma
de deuda que menos se ve porque el gate publica verde con ella dentro. Este
gate no lo tiene y no lo va a tener: el directorio nace vacio, asi que no hay
deuda heredada que congelar. Ver la tarea #219.

*Metrica:* presencia y forma de las cinco claves obligatorias en el
``manifest.json`` de cada subdirectorio de ``scripts/workbench/``.
*Ciega a:* si lo declarado es CIERTO — un ``metric`` que describa otra cosa
pasa igual que uno exacto. Eso lo mide quien revisa, no un gate de forma.

Uso::

    python3 scripts/check_workbench.py            # reporte
    python3 scripts/check_workbench.py --strict   # exit 1 si hay incumplidores
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
WORKBENCH = REPO / 'scripts' / 'workbench'
SCHEMA = WORKBENCH / 'manifest_schema.json'

#: Los archivos del propio banco, que no son piezas de trabajo.
BENCH_FILES = {'README.md', 'manifest_schema.json'}


def required_keys(schema_path=SCHEMA):
    """Las obligatorias salen del esquema, no de una copia en este archivo.

    Duplicar la lista aqui crearia la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohibe: el esquema y el gate
    divergirian y los dos seguirian dando un numero.
    """
    if not schema_path.is_file():
        # Rehusa con codigo propio en vez de medir con una lista inventada:
        # un 0 sin esquema no distingue "todo cumple" de "no pude medir".
        print(f'ERROR — falta el esquema en {schema_path}. No se emite conteo: '
              'un 0 aqui seria un verde falso.', file=sys.stderr)
        raise SystemExit(2)
    return list(json.loads(schema_path.read_text())['required'])


def work_dirs(root=WORKBENCH):
    """Los subdirectorios que son piezas de trabajo."""
    if not root.is_dir():
        return []
    return sorted(d for d in root.iterdir()
                  if d.is_dir() and d.name not in BENCH_FILES
                  and not d.name.startswith(('.', '__')))


def offences_of(directory, keys):
    """Que le falta a esta pieza de trabajo. Lista vacia = cumple."""
    manifest = directory / 'manifest.json'
    if not manifest.is_file():
        return ['no declara manifest.json']
    try:
        declared = json.loads(manifest.read_text())
    except json.JSONDecodeError as error:
        return [f'manifest.json no es JSON valido: {error}']
    if not isinstance(declared, dict):
        return ['manifest.json no declara un objeto']

    found = []
    for key in keys:
        if key not in declared:
            found.append(f'falta la clave obligatoria {key!r}')
        elif not declared[key]:
            # Una clave presente y vacia es peor que ausente: parece
            # declarada. Es la misma forma que el verde que no discrimina.
            found.append(f'la clave {key!r} esta vacia')
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si hay piezas de trabajo incumplidoras')
    args = parser.parse_args()

    keys = required_keys()
    directories = work_dirs()
    offenders = {d: found for d in directories
                 if (found := offences_of(d, keys))}

    for directory, found in offenders.items():
        print(f'  {directory.relative_to(REPO)}')
        for one in found:
            print(f'      {one}')

    print(f'check_workbench: {len(offenders)} incumplidor(es) '
          f'(alcance medido: {len(directories)} pieza(s) de trabajo; '
          f'{len(keys)} clave(s) obligatoria(s) leidas del esquema; '
          'sin baseline por directiva del ejecutor 2026-08-30)')
    if offenders and args.strict:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
