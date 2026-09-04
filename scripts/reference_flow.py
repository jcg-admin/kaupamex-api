#!/usr/bin/env python3
"""Leer el FLUJO de un simbolo de la referencia ANTES de portarlo.

El defecto que este guion ataca lo registro :ref:`h-api-1072`: se porta el
simbolo, se lee su cuerpo, y el contrato que gobierna vive **fuera** — en una
base de su clase, en quien lo llama, o en un hermano que declara lo mismo. El
porte sale coherente consigo mismo y divergente del flujo real, y eso no lo ve
ningun gate: los de este arbol miden presencia, cabecera, sitio o nombre.

**Cinco unidades de lectura**, y las cinco se publican juntas:

1. **el simbolo** — donde se declara, con que firma;
2. **sus bases** — el contrato puede estar arriba en la jerarquia;
3. **quien lo llama** — el flujo casi nunca esta dentro del simbolo;
4. **sus hermanos** — otras clases que declaran el mismo nombre;
5. **el instrumento** — que mide y que sobre-captura, declarado en la salida.

**Por que sobre** ``counterpart_body`` **y no al lado.** Ese modulo ya posee el
mapa de raices espejadas (``MIRRORED_ROOTS``), el extractor de llamadas
(``called_names``), el de declaraciones (``declarations_of``) y el denominador
(``Scope``). Construir un recorrido paralelo duplicaria el mapa de rutas, que
es la segunda fuente de verdad que ``calibration-verified-numbers.md`` prohibe
y que ya se pago una vez en :ref:`h-api-335`.

**Los siete factores, pesados para este caso concreto.** El *rendimiento* manda
la unica decision de diseno no obvia: la arista de vuelta (quien llama) es
cuadratica sobre el arbol, y la referencia tiene cientos de miles de archivos.
Por eso el alcance **se declara y se acota** a raices dadas, en vez de barrer
todo — y por eso el informe imprime siempre sobre cuantos archivos midio. La
*claridad* pide que las cinco unidades salgan juntas aunque alguna venga
vacia: una unidad ausente del informe se lee como "no aplica", y una vacia
como "medido, no hay". La *seguridad* es de solo lectura: ni un ``checkout``
sobre ``odoo-tools``.

Uso::

    python3 scripts/reference_flow.py --symbol config_filename
    python3 scripts/reference_flow.py --file odoo/tools/mimetypes.py
    python3 scripts/reference_flow.py --symbol frozendict --root odoo/orm
"""
import argparse
import ast
import collections
import dataclasses
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import counterpart_body  # noqa: E402 — el motor: rutas, AST y denominador
import reference_roots  # noqa: E402 — la raiz se declara una vez (H-API-335)

#: Las raices que se miden cuando nadie las declara: **el arbol entero**.
#: Fue ``('odoo/tools', 'odoo/orm', 'odoo/addons/base')`` hasta que el prefiltro
#: de ``files_naming`` hizo barato medirlo todo. Un default estrecho publicaba
#: ceros falsos —``parse_inline_template`` daba 0 llamadores con su consumidor
#: real en ``addons/mail``— y un cero de un instrumento que no alcanza es peor
#: que ninguna cifra. Acotar sigue siendo posible con ``--root``, y entonces el
#: informe dice sobre cuantos archivos midio.
DEFAULT_ROOTS = ('odoo', 'addons')

#: Lo que el instrumento NO puede ver, declarado junto al resultado en vez de
#: en un comentario que nadie lee (``metrica-decide-la-conclusion.md``).
BLIND_SPOTS = (
    'la llamada dinamica (getattr, despacho por cadena) no deja arista',
    'la llamada desde XML, CSV o data no se lee: el alcance es .py',
    'el receptor de una llamada por atributo no se resuelve a su clase, '
    'asi que un homonimo de otra clase cuenta como llamador',
    'un llamador fuera de las raices medidas no aparece',
)


@dataclasses.dataclass(frozen=True)
class CallSite:
    """Un sitio que invoca el nombre, con su duena."""

    path: str
    lineno: int
    owner: str
    caller: str

    def __str__(self):
        where = f'{self.owner}.{self.caller}' if self.owner else self.caller
        return f'{self.path}:{self.lineno}  {where}'


@dataclasses.dataclass(frozen=True)
class FlowScope:
    """El denominador, con sus DOS cifras: no se colapsan en una.

    ``files_in_universe`` es cuanto abarca la medicion; ``files_parsed``, de
    cuantos se leyo el AST tras el prefiltro. Publicar solo la segunda diria
    "alcance medido: 2 archivos" de un barrido que cubrio 8476 — un encabezado
    unico sobre dos metricas distintas, que es el sub-patron A de
    ``metrica-decide-la-conclusion.md``.
    """

    files_in_universe: int
    files_parsed: int
    declarations: int


@dataclasses.dataclass(frozen=True)
class Flow:
    """Las cinco unidades de lectura de un simbolo, con su alcance."""

    symbol: str
    declarations: tuple
    bases_declaring: tuple
    callers: tuple
    siblings: tuple
    scope: FlowScope


def resolve_roots(roots):
    """Las raices pedidas, resueltas contra el arbol de la referencia."""
    tree = reference_roots.tree()
    resolved = []
    for root in roots:
        candidate = pathlib.Path(root)
        resolved.append(candidate if candidate.is_absolute()
                        else tree / root)
    return resolved


def universe_files(roots):
    """Los ``.py`` de las raices, listados una vez. No parsea nada."""
    return list(counterpart_body.tree_files(roots))


def files_naming(files, names):
    """Los archivos cuyo TEXTO menciona alguno de los nombres.

    Es el prefiltro que hace viable medir el arbol entero, y esa viabilidad no
    es comodidad: con las tres raices por defecto, ``parse_inline_template``
    reporta **0 llamadores** — y su consumidor real vive en
    ``addons/mail/models/mail_render_mixin.py``, fuera de ellas. Ese cero es
    el verde que no discrimina: no distingue "nadie lo llama" de "el alcance
    no alcanza a quien lo llama".

    Un archivo que no escribe el nombre no puede declararlo, llamarlo ni
    heredarlo, asi que parsear su AST no aporta arista. Leer bytes cuesta
    ordenes de magnitud menos que ``ast.parse``: medido sobre los 8476
    archivos ``.py`` de la referencia, 0.11 s de prefiltro y 0.01 s de AST
    sobre los 2 candidatos.

    Ciego a la llamada cuyo nombre se arma en ejecucion
    (``getattr(obj, 'pre' + 'fijo')``) — la misma ceguera que ``BLIND_SPOTS``
    ya declara para el despacho dinamico, no una nueva.
    """
    needles = [name.encode() for name in names]
    found = []
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if any(needle in data for needle in needles):
            found.append(path)
    return found


def index_files(files):
    """Un indice ``ruta -> (arbol, declaraciones)`` de los archivos dados.

    Se parsea **una vez** por archivo: las cuatro unidades leen del mismo
    indice.
    """
    index = {}
    for path in files:
        tree = counterpart_body.parse_file(path)
        if tree is None:
            continue
        index[path] = (tree, counterpart_body.declarations_of(path, tree))
    return index


def index_roots(roots, names=None):
    """El indice de las raices; con ``names``, solo de los que los mencionan."""
    files = universe_files(roots)
    if names is not None:
        files = files_naming(files, names)
    return index_files(files)


def declarations_named(index, symbol):
    """Donde se declara el simbolo, en todo el alcance medido."""
    return tuple((path, decl) for path, (_, decls) in index.items()
                 for decl in decls if decl.name == symbol)


def bases_declaring(index, declarations, symbol):
    """Las bases de la clase duena que TAMBIEN declaran el nombre.

    Es la unidad 2: si una base lo declara, el contrato que gobierna puede ser
    el suyo y no el de la clase que se estaba leyendo.
    """
    wanted = {base for _, decl in declarations for base in decl.bases}
    if not wanted:
        return ()
    found = []
    for path, (_, decls) in index.items():
        for decl in decls:
            if decl.owner in wanted and decl.name == symbol:
                found.append((path, decl))
    return tuple(found)


def callers_of(index, symbol, declared_at):
    """Los sitios que invocan el nombre, sin contar su propia declaracion.

    Una declaracion de **clase** se salta a proposito: ``called_names``
    recorre todo su cuerpo, asi que la clase heredaria las llamadas de cada
    uno de sus metodos y cada llamador saldria dos veces —la clase y el
    metodo—. Los metodos ya estan en el indice por separado; contar tambien
    su clase infla el numerador sin anadir un sitio real.
    """
    own = {(path, decl.lineno) for path, decl in declared_at}
    sites = []
    for path, (_, decls) in index.items():
        for decl in decls:
            if decl.kind == 'class' or (path, decl.lineno) in own:
                continue
            if symbol in set(counterpart_body.called_names(decl.node)):
                sites.append(CallSite(str(path), decl.lineno,
                                      decl.owner, decl.name))
    return tuple(sites)


def siblings_of(index, symbol, origin=None):
    """Las clases del alcance que declaran el mismo nombre.

    Unidad 4: si el nombre lo declaran quince clases, el contrato es del
    conjunto, y portarlo mirando una sola es leer un quinceavo del contrato.

    ``origin`` es el archivo desde el que se pregunta, cuando lo hay: entonces
    *hermano* significa **fuera de ese archivo**. Sin origen —al preguntar por
    un nombre suelto— hermano es toda clase duena, porque no hay un "aqui"
    contra el que sea otra. Excluirlas todas contra si mismas daba cero
    hermanos justo cuando mas hay, que es el verde que no discrimina.
    """
    return tuple(sorted({decl.owner for path, (_, decls) in index.items()
                         for decl in decls
                         if decl.name == symbol and decl.owner
                         and (origin is None or pathlib.Path(path) != origin)}))


def flow_of(symbol, index, origin=None, universe=None):
    """Las cinco unidades del simbolo sobre el indice ya construido.

    ``universe`` es el tamano del alcance ANTES del prefiltro. Sin el, el
    informe publicaria como denominador el numero de archivos que sobrevivieron
    al filtro, que es la cifra equivocada.
    """
    declared = declarations_named(index, symbol)
    return Flow(
        symbol=symbol,
        declarations=declared,
        bases_declaring=bases_declaring(index, declared, symbol),
        callers=callers_of(index, symbol, declared),
        siblings=siblings_of(index, symbol, origin),
        scope=FlowScope(
            files_in_universe=len(index) if universe is None else universe,
            files_parsed=len(index),
            declarations=len(declared)),
    )


def symbols_of_file(path):
    """Los nombres declarados en un archivo de la referencia."""
    return tuple(sorted({decl.name
                         for decl in counterpart_body.declarations_of(path)}))


def render(flow, tree_root):
    """El informe de un simbolo. Una unidad vacia se imprime igual."""
    def short(path):
        try:
            return str(pathlib.Path(path).relative_to(tree_root))
        except ValueError:
            return str(path)

    out = [f'== {flow.symbol}']
    if not flow.declarations:
        out.append('   declara      : (no se declara en el alcance medido)')
    for path, decl in flow.declarations:
        where = f'{decl.owner}.{decl.name}' if decl.owner else decl.name
        bases = f'  bases={list(decl.bases)}' if decl.bases else ''
        out.append(f'   declara      : {short(path)}:{decl.lineno}  '
                   f'{where}{bases}')
    out.append(f'   bases con el : {len(flow.bases_declaring)}')
    for path, decl in flow.bases_declaring:
        out.append(f'                  {short(path)}:{decl.lineno}  '
                   f'{decl.owner}.{decl.name}')
    out.append(f'   lo llaman    : {len(flow.callers)}')
    for site in flow.callers[:20]:
        out.append(f'                  {short(site.path)}:{site.lineno}  '
                   f'{site.owner + "." if site.owner else ""}{site.caller}')
    if len(flow.callers) > 20:
        out.append(f'                  (+{len(flow.callers) - 20} mas)')
    out.append(f'   hermanos     : {len(flow.siblings)}'
               + (f'  {list(flow.siblings[:12])}' if flow.siblings else ''))
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--symbol', action='append', default=[],
                        help='nombre a analizar; repetible')
    parser.add_argument('--file', default=None,
                        help='archivo de la referencia: analiza sus simbolos')
    parser.add_argument('--root', action='append', default=[],
                        help=f'raiz a medir; default {list(DEFAULT_ROOTS)}')
    parser.add_argument('--alias', default='odoo19c',
                        help='alias del arbol de referencia')
    args = parser.parse_args(argv)

    tree_root = reference_roots.tree(args.alias)
    roots = resolve_roots(args.root or DEFAULT_ROOTS)
    missing = [r for r in roots if not r.exists()]
    if missing:
        print('ERROR — raiz inexistente: '
              + ', '.join(str(r) for r in missing)
              + '. NO se emite informe: un alcance vacio publicaria "0 '
                'llamadores" y ese cero seria un verde falso.',
              file=sys.stderr)
        return 2

    symbols = list(args.symbol)
    if args.file:
        target = pathlib.Path(args.file)
        if not target.is_absolute():
            target = tree_root / args.file
        if not target.is_file():
            print(f'ERROR — no existe: {target}', file=sys.stderr)
            return 2
        symbols.extend(symbols_of_file(target))
    if not symbols:
        parser.error('se requiere --symbol o --file')

    symbols = list(dict.fromkeys(symbols))
    files = universe_files(roots)
    index = index_files(files_naming(files, symbols))

    # Segunda pasada. Las bases solo se conocen tras leer las declaraciones, y
    # el contrato que gobierna puede vivir en una base declarada en OTRO
    # archivo, que el prefiltro del simbolo no trajo. Sin esta pasada la
    # unidad 2 publicaria 0 bases cada vez que la base vive aparte.
    bases = {base for symbol in symbols
             for _, decl in declarations_named(index, symbol)
             for base in decl.bases}
    if bases:
        index.update(index_files(
            path for path in files_naming(files, sorted(bases))
            if path not in index))

    origin = target if args.file else None
    for symbol in symbols:
        print(render(flow_of(symbol, index, origin, len(files)), tree_root))
    print(f'\nreference_flow: {len(symbols)} simbolo(s) '
          f'(alcance medido: {len(files)} archivo(s) .py sobre '
          f'{len(roots)} raiz(ces): '
          + ', '.join(str(r.relative_to(tree_root)) if r.is_relative_to(
              tree_root) else str(r) for r in roots)
          + f'; {len(index)} parseado(s) tras el prefiltro por nombre)')
    print('Ciega a: ' + '; '.join(BLIND_SPOTS) + '.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
