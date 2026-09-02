"""Donde vive ya cada simbolo ausente de ``odoo/orm/``: el eje de inventario.

El censo hermano (``orm-root-census-*``) responde **que falta**. Este responde
la pregunta anterior a portar: **con que se construye lo que falta**, bajo el
criterio de dos categorias que gobierna este proyecto:

- **el stack lo trae hecho** — hay un simbolo instalado y basta llamarlo;
- **el stack tiene con que construirlo** — no hay simbolo hecho, pero las
  primitivas estan y no hace falta ninguna dependencia de fuera.

Por que el instrumento NO emite el veredicto
=============================================

Emitirlo seria el sub-patron C de ``metrica-decide-la-conclusion.md``: se mide
la **forma** (existe un nombre) y se concluye sobre el **fondo** (ese simbolo
hace lo que el de la fuente hace). ``create``, ``write`` y ``read`` se declaran
en decenas de sitios del stack y ninguno es el de la referencia.

Lo que este guion produce es el **material medido** sobre el que se escribe el
veredicto, repartido en cuatro cubos:

===================  ===================================================
``ya_esta_aqui``     **un solo** archivo de NUESTRO arbol lo declara,
                     fuera de la raiz espejada. No es trabajo de porte: es
                     reubicacion o declaracion de sitio (la clase de
                     :ref:`h-api-578`)
``trae_candidato``   lo declara **exactamente un** paquete del stack. El
                     nombre es especifico, asi que la coincidencia es una
                     pista real y el veredicto se decide leyendo ese
                     simbolo
``nombre_generico``  lo declaran **dos o mas** paquetes del stack, o dos o
                     mas archivos nuestros. El nombre no dice nada — ``add``,
                     ``read`` y ``__setitem__`` viven en todas partes; el
                     veredicto exige leer la fuente y el candidato
``sin_rastro``       no lo declara nadie, ni el stack ni nosotros. Cae por
                     defecto en «se construye»: es lo que la regla
                     ``porte-completo-no-parcial.md`` ya manda
===================  ===================================================

Se mide por AST, no por texto
==============================

Un nombre que aparece en el CUERPO de una funcion no es un simbolo que se
pueda llamar. Medir por ``grep`` daria por presente una variable local y el
veredicto diria «el stack lo trae hecho» sobre nada. El control de esa
distincion es un caso de la suite, no una promesa del docstring.

*Metrica:* nombres declarados como ``def``/``class`` —a nivel de modulo o
dentro de una clase— en los archivos ``.py`` de las raices que se le pasen.
*Ciega a:* que el simbolo encontrado **haga** lo que el de la fuente hace —
esa es la mitad que el veredicto escribe a mano; al simbolo que el stack
expone con OTRO nombre (``frozendict`` de la fuente contra
``MappingProxyType`` de la stdlib), que cae en ``sin_rastro`` siendo un
``trae``; y a todo lo que un paquete expone por C, por ``__getattr__`` o por
reexportacion en ``__init__``.
"""
import argparse
import ast
import collections
import dataclasses
import pathlib
import sys
import warnings

#: Los cubos, en el orden de precedencia con que se resuelven.
BUCKETS = ('ya_esta_aqui', 'trae_candidato', 'nombre_generico', 'sin_rastro')


def declarations_in(path):
    """Los nombres que ``path`` **declara** como funcion o clase.

    Un archivo que no parsea devuelve el conjunto vacio: el indice recorre
    miles de archivos instalados y uno con sintaxis de otra version de Python
    no puede tumbar la medicion. Tampoco puede inventar: vacio es vacio, no
    una excusa para adivinar por texto.
    """
    try:
        with warnings.catch_warnings():
            # La stdlib trae archivos de prueba con secuencias de escape que
            # ``compile`` denuncia. El aviso describe ESE archivo, no nuestra
            # medicion, y en la salida taparia la cifra que se busca.
            warnings.simplefilter('ignore', SyntaxWarning)
            tree = ast.parse(path.read_text(encoding='utf-8',
                                            errors='replace'))
    except (SyntaxError, ValueError, OSError):
        return set()
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef))
    }


def index_declarations(roots):
    """``{nombre: {paquete: {ruta, ...}}}`` sobre las raices dadas.

    El **paquete** es el primer segmento bajo la raiz — es el eje de la
    especificidad. Dos archivos del mismo paquete no vuelven generico a un
    nombre; dos paquetes distintos si.

    Una raiz inexistente levanta ``FileNotFoundError`` en vez de aportar cero
    archivos: un indice vacio por una ruta mal escrita publicaria «el stack no
    lo trae» sobre todo, y ese verde no distinguiria «no lo trae nadie» de «no
    pude medir».
    """
    index = collections.defaultdict(lambda: collections.defaultdict(set))
    for root in roots:
        root = pathlib.Path(root)
        if not root.is_dir():
            raise FileNotFoundError(
                f'{root} no existe; sin ella el indice no mide nada y su cero '
                'seria un verde falso')
        for py in root.rglob('*.py'):
            relative = py.relative_to(root)
            package = relative.parts[0] if len(relative.parts) > 1 else py.stem
            for name in declarations_in(py):
                index[name][package].add(str(py))
    return {name: dict(packages) for name, packages in index.items()}


def classify(symbol, stack_index, ours_index):
    """El cubo de un simbolo, con ``ya_esta_aqui`` por delante de todo.

    Nuestro arbol gana la precedencia porque cambia el trabajo: un simbolo que
    ya escribimos no se porta ni se construye — se reubica, o se declara por
    que vive donde vive.

    La especificidad se exige **en los dos universos**, no solo en el stack:
    ``add`` lo declaran tres archivos nuestros y ninguno es el de la fuente.
    Sin esa simetria el cubo se llena de dunders y verbos genericos, y una
    cota superior contaminada se lee como inventario.
    """
    ours = ours_index.get(symbol)
    if ours:
        return 'ya_esta_aqui' if len(ours) == 1 else 'nombre_generico'
    packages = stack_index.get(symbol)
    if not packages:
        return 'sin_rastro'
    return 'trae_candidato' if len(packages) == 1 else 'nombre_generico'


def evidence(symbol, stack_index, ours_index):
    """Las rutas que sostienen el cubo de ``symbol``, vengan de donde vengan.

    ``nombre_generico`` lo puede producir CUALQUIERA de los dos universos —dos
    paquetes del stack, o dos archivos nuestros—, asi que leer la evidencia
    solo del stack revienta con ``KeyError`` sobre un generico nuestro. Ocurrio
    al correrlo: ``_read_group_select``, declarado en dos addons y en ningun
    paquete instalado.
    """
    ours = sorted(ours_index.get(symbol, ()))
    stack = sorted({ruta for rutas in stack_index.get(symbol, {}).values()
                    for ruta in rutas})
    return ours + stack


@dataclasses.dataclass
class Total:
    """El agregado, siempre con su universo al lado."""

    universe: int
    by_bucket: dict


def summary(symbols, stack_index, ours_index):
    """Reparte ``symbols`` en los cuatro cubos y publica su denominador."""
    counts = dict.fromkeys(BUCKETS, 0)
    for symbol in symbols:
        counts[classify(symbol, stack_index, ours_index)] += 1
    return Total(universe=len(symbols), by_bucket=counts)


def our_declarations_outside(root_name):
    """Lo que declaramos en ``src`` y ``addons`` FUERA de la raiz espejada.

    Es el universo que el censo por archivo no puede ver: su alcance de
    resolucion es la raiz, y un simbolo que aterrizo en ``src/tools`` le
    consta como ausente.
    """
    excluded = pathlib.Path('src') / root_name
    index = collections.defaultdict(set)
    for root in (pathlib.Path('src'), pathlib.Path('addons')):
        if not root.is_dir():
            continue
        for py in root.rglob('*.py'):
            if excluded in py.parents:
                continue
            for name in declarations_in(py):
                index[name].add(str(py))
    return dict(index)


def absent_symbols(root_name):
    """Los ausentes que publica el censo hermano, por archivo de la fuente."""
    census_dir = sorted(
        pathlib.Path('scripts/workbench').glob('orm-root-census-*'))[-1]
    sys.path.insert(0, str(census_dir))
    import census_orm_root as census  # noqa: PLC0415 — vive fuera del paquete

    ref, mine = census._roots(root_name)
    if not ref.is_dir():
        raise FileNotFoundError(
            f'no esta la raiz de referencia en {ref}; sin ella no hay ausentes '
            'que clasificar')
    rows = census.census(ref, mine)
    return {row.name: list(row.missing) + list(row.missing_classes)
            for row in rows.values()}


def stack_roots():
    """Las raices del stack instalado y de la biblioteca estandar."""
    site = sorted(pathlib.Path('.venv/lib').glob('python3.*/site-packages'))
    if not site:
        raise FileNotFoundError(
            'no esta .venv/lib/python3.*/site-packages; sin el stack instalado '
            'este censo no puede distinguir TRAE de CONSTRUYE')
    stdlib = pathlib.Path(sysconfig_stdlib())
    return [site[-1], stdlib]


def sysconfig_stdlib():
    """La raiz de la biblioteca estandar del interprete que corre."""
    import sysconfig  # noqa: PLC0415 — solo lo necesita esta funcion

    return sysconfig.get_paths()['stdlib']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='orm',
                        help='la raiz espejada cuyos ausentes se clasifican')
    parser.add_argument('--detalle', action='store_true',
                        help='listar cada simbolo con su cubo y su evidencia')
    args = parser.parse_args(argv)

    por_archivo = absent_symbols(args.root)
    todos = sorted({s for lista in por_archivo.values() for s in lista})
    stack = index_declarations(stack_roots())
    ours = our_declarations_outside(args.root)

    total = summary(todos, stack, ours)
    print(f'=== ausentes de odoo/{args.root}: en que universo vive su nombre ===\n')
    for bucket in BUCKETS:
        n = total.by_bucket[bucket]
        pct = 100.0 * n / total.universe if total.universe else 0.0
        print(f'{bucket:<18} {n:>5}  ({pct:5.1f} %)')
    print(f'\nuniverso: {total.universe} simbolo(s) ausente(s) distintos '
          f'en {len(por_archivo)} archivo(s) de la referencia')
    print(f'indice del stack: {len(stack)} nombre(s) declarado(s); '
          f'nuestro arbol fuera de src/{args.root}: {len(ours)}')

    if args.detalle:
        print()
        for symbol in todos:
            bucket = classify(symbol, stack, ours)
            donde = ', '.join(evidence(symbol, stack, ours)[:3])
            print(f'{bucket:<18} {symbol:<44} {donde}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
