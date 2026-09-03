"""Censa la deuda congelada de identificadores en espanol, por palabra y por raiz.

La pregunta la fija ``manifest.json``: si la deuda se puede barrer con el
instrumento que ya existe. La respuesta sale de agrupar el baseline por la
**palabra espanola** que lo hizo entrar, no por el identificador entero: el
identificador ``obtener_nombre_del_producto`` no se traduce como un todo, se
traduce palabra a palabra, y ese es el mapa que el reescritor consume.

*Metrica:* entradas ``archivo::identificador`` del baseline, agrupadas.
*Ciega a:* si dos entradas con el mismo nombre son la misma ligadura; al
identificador que el lexico del gate no sabe ver (el baseline es cota inferior);
y a la colision de una traduccion con un nombre ya ligado en ese ambito.
"""
import argparse
import collections
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[3]
BASELINE = RAIZ / 'scripts' / 'identifier_language_baseline.txt'

sys.path.insert(0, str(RAIZ / 'scripts'))


def load_lexicon():
    """El lexico del gate, cargado por ruta — no una copia.

    Copiarlo seria la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohibe: el gate decide que palabra es
    espanola, y este censo tiene que agrupar por esa misma decision.
    """
    try:
        from check_identifier_language import spanish_words_in
    except ImportError as exc:
        print('ERROR — no se pudo cargar el lexico del gate '
              f'(scripts/check_identifier_language.py): {exc}\n'
              'NO se emite conteo: un 0 aqui seria un verde falso.',
              file=sys.stderr)
        raise SystemExit(2) from exc
    return spanish_words_in


def read_baseline(path):
    """Las entradas vivas del baseline, sin sus lineas de comentario."""
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        archivo, _, nombre = line.partition('::')
        if nombre:
            entries.append((archivo, nombre))
    return entries


def census(entries, spanish_words_in):
    """Reparte las entradas por raiz, por archivo y por palabra espanola."""
    by_root = collections.Counter()
    by_file = collections.Counter()
    by_word = collections.Counter()
    for archivo, nombre in entries:
        by_root[archivo.split('/', 1)[0]] += 1
        by_file[archivo] += 1
        for palabra in spanish_words_in(nombre):
            by_word[palabra] += 1
    return by_root, by_file, by_word


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true',
                        help='emite el censo como JSON en vez de tabla')
    parser.add_argument('--top', type=int, default=25,
                        help='cuantas filas mostrar en cada corte')
    args = parser.parse_args(argv)

    spanish_words_in = load_lexicon()
    entries = read_baseline(BASELINE)
    by_root, by_file, by_word = census(entries, spanish_words_in)

    if args.json:
        print(json.dumps({
            'entries': len(entries),
            'distinct_names': len({n for _, n in entries}),
            'files': len(by_file),
            'by_root': dict(by_root.most_common()),
            'by_word': dict(by_word.most_common()),
        }, ensure_ascii=False, indent=2))
        return 0

    print(f'entradas: {len(entries)} · nombres distintos: '
          f'{len({n for _, n in entries})} · archivos: {len(by_file)}')
    print('\npor raiz:')
    for raiz, cuantas in by_root.most_common():
        print(f'  {cuantas:5d}  {raiz}')
    print(f'\npor palabra espanola (top {args.top} de {len(by_word)}):')
    for palabra, cuantas in by_word.most_common(args.top):
        print(f'  {cuantas:5d}  {palabra}')
    print(f'\npor archivo (top {args.top}):')
    for archivo, cuantas in by_file.most_common(args.top):
        print(f'  {cuantas:5d}  {archivo}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
