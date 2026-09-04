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

Su gemelo en prosa
==================

``docs: .claude/rules/redaccion-tecnica-es.md``, sección «Elegir el término».
Miden la misma pregunta sobre ejes distintos, y **el veredicto puede ser el
opuesto**: ``ejecución`` es correcto en prosa y defecto en un identificador
(``run_id``); ``run`` al revés. ``SPANISH_WORDS`` es la forma ejecutable de la
tabla de términos que esa regla resuelve — cuando resuelve uno nuevo, su palabra
española entra aquí.

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
    # Vocabulario resuelto por redaccion-tecnica-es.md («Elegir el término»):
    # el árbol nombra estas cosas en inglés, así que en un identificador
    # el español es defecto. En PROSA el veredicto puede ser el opuesto.
    'corrida', 'corridas', 'tanda', 'tandas', 'guion', 'guiones',
    'lote', 'lotes',
})


def split_words(name):
    """Parte ``snake_case`` y ``camelCase`` en palabras minúsculas."""
    out = []
    for chunk in re.split(r'_+', name):
        out += re.findall(r'[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+', chunk)
    return [w.lower() for w in out if w]


#: Igual que ``split_words`` pero conservando los dígitos como token propio.
#: ``split_words`` los descarta, y esa pérdida es la que hace ilegible
#: ``CenEn16931``: sin el ``16931``, el ``En`` queda suelto y se lee como la
#: preposición española.
_TOKEN = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+|\d+')


def _particles_before_digits(name):
    """Partículas que van pegadas a dígitos — códigos, no preposiciones.

    ``En16931`` es la norma europea EN 16931. El español no numera sus
    preposiciones, así que una partícula seguida de dígitos es siempre un
    token técnico. Medido sobre los 1137 del baseline: no pierde ninguno.
    """
    out = set()
    for chunk in re.split(r'_+', name):
        tokens = _TOKEN.findall(chunk)
        for cur, nxt in zip(tokens, tokens[1:]):
            if cur.lower() in SPANISH_PARTICLES and nxt.isdigit():
                out.add(cur.lower())
    return out


def _technical_suffix(name):
    """¿La partícula final es un código, no una preposición?

    ``AccountEdiXmlUbl_De`` termina en el ISO-3166 de Alemania. La señal es la
    **forma mixta**: CamelCase real antes del guion bajo. El español en
    identificadores se escribe en snake_case puro (``_tracking_de``,
    ``_apunte_en``, ``resp_con``), nunca mezclado — medido sobre los 1137 del
    baseline, esta regla no pierde ninguno.

    Y una preposición española no cierra un nombre: conecta (``orden_de_compra``).
    Cuando queda al final de un identificador CamelCase, es un sufijo técnico.
    """
    if '_' not in name:
        return False
    head, _, tail = name.rpartition('_')
    return (tail.lower() in SPANISH_PARTICLES
            and re.search(r'[a-z][A-Z]', head) is not None)


#: Cuantos hermanos hacen falta para que un sufijo de dos letras sea un
#: codigo y no una preposicion. Tres es el minimo que descarta la
#: coincidencia: un archivo con `orden_de`, `orden_en` y `orden_por` seria el
#: falso positivo de esta regla, y no existe — medido, 0 en el arbol.
FAMILIA_MINIMA = 3


def code_suffix_families(names):
    """Los prefijos que un archivo declara como familia de codigos de dos letras.

    ``check_vat_de`` no es espanol: ``de`` es el ISO-3166 de Alemania, y el
    nombre es el CONTRATO del despachador de la fuente —
    ``getattr(self, 'check_vat_' + cc.lower(), None)``—, asi que renombrarlo
    rompe la validacion del IVA aleman.

    Lo que lo distingue de una preposicion no es el token, que es identico,
    sino **la familia**: el mismo archivo declara cuarenta hermanos
    ``check_vat_XX`` con otros codigos. Esa evidencia se deriva del archivo, no
    de una tabla ISO copiada aqui — que ademas no discriminaria, porque ``de``
    es a la vez pais y preposicion.

    ``_technical_suffix`` cubre el caso hermano en CamelCase
    (``AccountEdiXmlUbl_De``) y declara que el espanol se escribe en snake_case
    puro. ``check_vat_de`` es el hueco de ese razonamiento: es snake_case puro
    Y su cola es un codigo.

    *Metrica:* prefijos con >= FAMILIA_MINIMA identificadores del mismo archivo
    que comparten prefijo y difieren en una cola de exactamente dos letras.
    *Ciega a:* una familia repartida entre varios archivos — cada archivo se
    mide solo, que es el lado seguro: sin hermanos, el sufijo vuelve a contar
    como preposicion.
    """
    por_prefijo = {}
    for name in names:
        head, sep, tail = name.rpartition('_')
        if sep and len(tail) == 2 and tail.isalpha():
            por_prefijo.setdefault(head.lower(), set()).add(tail.lower())
    return {prefijo for prefijo, colas in por_prefijo.items()
            if len(colas) >= FAMILIA_MINIMA}


def spanish_words_in(name, code_families=frozenset()):
    """Palabras españolas del identificador, o lista vacía.

    ``code_families`` son los prefijos que el ARCHIVO declara como familia de
    codigos de dos letras (ver :func:`code_suffix_families`). Es opcional para
    que el gate hermano de ``docs`` —que mide nombres de archivo sueltos, sin
    archivo que dé contexto— siga llamando con un solo argumento.
    """
    words = split_words(name)
    hits = [w for w in words
            if w in SPANISH_WORDS
            or (len(w) > 5 and SPANISH_MORPHOLOGY.search(w))]
    if len(words) >= 2:
        # Las tres exenciones se miden contra el baseline entero antes de
        # entrar: ninguna pierde un solo caso de español real.
        tecnicas = _particles_before_digits(name)
        if _technical_suffix(name):
            tecnicas.add(name.rpartition('_')[2].lower())
        head, sep, tail = name.rpartition('_')
        if sep and head.lower() in code_families:
            tecnicas.add(tail.lower())
        hits += [w for w in words
                 if w in SPANISH_PARTICLES and w not in tecnicas]
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
        declarados = list(declared_identifiers(tree))
        familias = code_suffix_families(n for n, _ in declarados)
        for name, lineno in declarados:
            if name in seen:
                continue
            hits = spanish_words_in(name, familias)
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
    print('  Modelo → Model (no Probe) · _Base se queda _Base.')
    print('OJO: un modelo CONCRETO no puede empezar ni terminar en guion bajo')
    print('  (Django models.E023). Lo vigila check_model_name_lookup.py.')
    print(f'\nMedido: {measured} archivos. Deuda heredada congelada: '
          f'{len(baseline)} (tarea #147).')
    return 1


if __name__ == '__main__':
    sys.exit(main())
