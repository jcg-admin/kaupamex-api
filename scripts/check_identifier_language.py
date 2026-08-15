#!/usr/bin/env python3
"""Gate: los identificadores se escriben en inglés; los comentarios, en español.

Cierra la tarea #365 (``H-API-607``). Nace de una directiva reiterada del
ejecutor —*"los nombres de los archivos, clases, funciones y atributos son en
inglés, los comentarios sí pueden ir en español"*— que hasta hoy vivía sólo en
prosa (``redaccion-tecnica-es.md``). La prosa no lo previno: hizo falta que el
ejecutor interrumpiera la tarea para corregirlo, que es justo el coste que este
guion existe para eliminar.

Qué mira, y qué NO
==================

Mira **identificadores declarados**: clases, funciones, métodos, argumentos y
nombres asignados. NO mira docstrings, comentarios ni cadenas — ahí el español
es la convención, no el defecto.

Cómo decide que una palabra es española
========================================

Dos criterios, los dos derivados de medir el árbol, no de memoria:

1. **Morfología exclusiva** — sufijos que el inglés no produce (``-ción``,
   ``-dad``, ``-mente``, ``-ando``, ``-iendo``, ``-ador``, ``-encia``). Sólo
   sobre palabras de más de cinco letras, para no confundir ``dad`` o ``and``.
2. **Partículas de alta precisión** en un identificador de **dos o más**
   palabras. El umbral importa: una variable llamada ``y`` o ``la`` es una letra
   suelta, no una frase en español; ``devuelve_el_metodo`` sí lo es.

Se excluyen a propósito las partículas ambiguas con el inglés (``no``, ``son``,
``a``, ``un``, ``es``) y ``sin``, que es una función trigonométrica.

*Métrica:* palabras españolas en identificadores declarados, por AST.
*Ciega a:* un identificador español cuyas palabras existan también en inglés
(``lista``→no, pero ``total``, ``final``, ``normal`` sí pasan), y a cualquier
palabra fuera del léxico. Es una **cota inferior**: un 0 no prueba que no quede
español, prueba que no queda del que este instrumento sabe ver.

Baseline
========

La deuda heredada está congelada en ``scripts/identifier_language_baseline.txt``
(``archivo::identificador``). Un identificador ya listado no bloquea; uno nuevo,
sí. Mismo criterio prospectivo que el mapa de capas de ``H-API-238`` y el grifo
cerrado de la tarea #313: se paga al tocar, no en un barrido.
"""
import argparse
import ast
import pathlib
import re
import sys

ROOTS = ('src', 'tests', 'addons')
BASELINE = pathlib.Path(__file__).with_name('identifier_language_baseline.txt')

#: Sufijos que el inglés no produce. Se exigen sobre palabras de >5 letras.
SPANISH_MORPHOLOGY = re.compile(
    r'(cion|ciones|dades?|mente|ando|iendo|adora?|encia|anza)$'
)

#: Partículas inequívocas. Sólo cuentan en identificadores de 2+ palabras.
#: Excluidas por ambigüedad con el inglés: no, son, a, un, e, i, o, y, es, sin.
SPANISH_PARTICLES = frozenset({
    'el', 'los', 'las', 'del', 'una', 'unos', 'unas', 'que', 'con', 'por',
    'para', 'desde', 'hasta', 'sobre', 'entre', 'cuando', 'donde', 'porque',
    'segun', 'sus', 'de', 'en',
})

#: Palabras de contenido que la morfología no atrapa, medidas en este árbol.
SPANISH_WORDS = frozenset({
    'producto', 'orden', 'usuario', 'cliente', 'precio', 'fecha', 'modelo',
    'nombre', 'campo', 'valor', 'codigo', 'linea', 'factura', 'pago', 'envio',
    'empresa', 'prueba', 'sonda', 'devuelve', 'rechaza', 'admite', 'crea',
    'barrido', 'marcado', 'privado', 'heredado', 'publico', 'estatico',
    'clase', 'metodo', 'atributo', 'archivo', 'ejemplo', 'tarea', 'datos',
    'tienda', 'carrito', 'pedido', 'entrega', 'moneda', 'impuesto', 'cuenta',
    'asiento', 'almacen', 'existencia', 'comprador', 'vendedor', 'cobro',
})


def split_words(name):
    """Parte ``snake_case`` y ``camelCase`` en palabras minúsculas."""
    out = []
    for chunk in re.split(r'_+', name):
        out += re.findall(r'[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+', chunk)
    return [w.lower() for w in out if w]


def spanish_words_in(name):
    """Palabras españolas del identificador, o lista vacía."""
    words = split_words(name)
    hits = [w for w in words
            if w in SPANISH_WORDS
            or (len(w) > 5 and SPANISH_MORPHOLOGY.search(w))]
    if len(words) >= 2:
        hits += [w for w in words if w in SPANISH_PARTICLES]
    return sorted(set(hits))


def declared_identifiers(tree):
    """Los identificadores que el archivo **declara**, con su línea.

    Los docstrings y comentarios quedan fuera por construcción: el AST no los
    entrega como nombre de nada.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            yield node.id, node.lineno


def load_baseline():
    if not BASELINE.exists():
        return set()
    return {line.strip() for line in BASELINE.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def scan(paths):
    """Devuelve ``(violaciones, archivos_medidos)``."""
    findings, measured = [], 0
    for path in paths:
        if 'migrations' in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        measured += 1
        seen = set()
        for name, lineno in declared_identifiers(tree):
            if name in seen:
                continue
            hits = spanish_words_in(name)
            if hits:
                seen.add(name)
                findings.append((str(path), name, lineno, hits))
    return findings, measured


def collect(argv_paths):
    if argv_paths:
        return [pathlib.Path(p) for p in argv_paths if p.endswith('.py')]
    files = []
    for root in ROOTS:
        files += sorted(pathlib.Path(root).rglob('*.py'))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='archivos a medir (default: todo el árbol)')
    parser.add_argument('--write-baseline', action='store_true',
                        help='congela el estado actual como deuda heredada')
    args = parser.parse_args()

    findings, measured = scan(collect(args.paths))

    if args.write_baseline:
        lines = sorted({f'{path}::{name}' for path, name, _, _ in findings})
        BASELINE.write_text(
            '# Deuda heredada de identificadores en español (tarea #147).\n'
            '# Congelada por check_identifier_language.py --write-baseline.\n'
            '# Un identificador NUEVO no entra aquí: se escribe en inglés.\n'
            + '\n'.join(lines) + '\n')
        print(f'baseline escrita: {len(lines)} identificadores '
              f'({measured} archivos medidos)')
        return 0

    baseline = load_baseline()
    fresh = [f for f in findings if f'{f[0]}::{f[1]}' not in baseline]

    if not fresh:
        print(f'OK: identificadores en inglés ({measured} archivos medidos, '
              f'{len(baseline)} en deuda heredada).')
        return 0

    print(f'FAIL — {len(fresh)} identificador(es) en español fuera del baseline:\n')
    for path, name, lineno, hits in fresh:
        print(f'  {path}:{lineno}  {name}   →  {", ".join(hits)}')
    print('\nLos identificadores van en INGLÉS; los comentarios y docstrings, en')
    print('español. Traducir el nombre, no buscarle un sinónimo más evocador:')
    print('  _Modelo → _Model (no _Probe) · _Base se queda _Base.')
    print(f'\nMedido: {measured} archivos. Deuda heredada congelada: '
          f'{len(baseline)} (tarea #147).')
    return 1


if __name__ == '__main__':
    sys.exit(main())
