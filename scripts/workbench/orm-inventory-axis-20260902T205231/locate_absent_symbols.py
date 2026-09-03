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
``trae_renombrado``  el stack declara el MISMO mecanismo con otro nombre, y
                     una fila de ``STACK_RENAME`` lo dice — con el
                     ``file:line`` de la fuente que la justifica. Cubo aparte
                     de ``trae_candidato`` a proposito: aquel dice «el stack
                     declara ESE nombre», este dice «alguien decidio a mano
                     que ESTE otro es el mismo mecanismo», y un solo
                     encabezado sobre las dos metricas es el sub-patron A
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
esa es la mitad que el veredicto escribe a mano; al simbolo renombrado que
**nadie puso en el mapa** —``STACK_RENAME`` cubre las tres familias que se
midieron, no el universo, asi que un ``sin_rastro`` sigue pudiendo ser un
``trae`` que nadie ha leido—; y a todo lo que un paquete expone por C, por
``__getattr__`` o por reexportacion en ``__init__``.
"""
import argparse
import ast
import collections
import dataclasses
import pathlib
import sys
import warnings

#: Los cubos, en el orden de precedencia con que se resuelven.
BUCKETS = ('ya_esta_aqui', 'trae_candidato', 'trae_renombrado',
           'nombre_generico', 'sin_rastro')

#: El mismo mecanismo, otro nombre: ``nombre_referencia -> nombre_stack``.
#:
#: NO es una traduccion de vocabulario entre dos ORM. Es una lista de
#: decisiones tomadas una por una **leyendo el cuerpo de la referencia**, con el
#: mismo criterio con que ``scripts/check_porte_completo.py::PORTE_ALIAS`` se
#: niega a aliasar ``write`` a ``save``: una fila de mas convierte una pregunta
#: abierta en una absolucion silenciosa.
#:
#: Cada fila cita el ``file:line`` de la fuente que la justifica, medido sobre
#: ``odoo19c`` con ``reference_roots.py --env``. El destino se comprueba contra
#: el indice del stack en cada ejecucion: una fila cuyo destino no exista se
#: reporta como muerta y NO mueve de cubo a su simbolo.
STACK_RENAME = {
    # --- Composicion de SQL: un nodo se renderiza a un fragmento -------------
    # ``def to_sql(self, model, alias) -> SQL`` (fields.py:1209,
    # fields_misc.py:122, fields_relational.py:466, fields_textual.py:394).
    # Django lo hace en ``as_sql(compiler, connection)`` sobre la expresion.
    'to_sql': 'as_sql',
    # ``def _to_sql(self, model, alias, query) -> SQL`` (domains.py:470, 522,
    # 571, 671) — el nodo del arbol de dominio. Django: ``WhereNode.as_sql``.
    '_to_sql': 'as_sql',
    # ``def condition_to_sql(self, field_expr, operator, value, model, alias,
    # query) -> SQL`` (fields_binary.py:233, fields_relational.py:480 y 779,
    # fields_properties.py:678) — el fragmento de un WHERE. Django: el
    # ``as_sql`` del ``Lookup``.
    'condition_to_sql': 'as_sql',
    '_condition_to_sql': 'as_sql',
    # ``def _order_to_sql(self, order, query, alias, reverse) -> SQL``
    # (models.py:5224) y ``_order_field_to_sql`` (models.py:5262) — el ORDER BY
    # sin su palabra clave. Django lo arma en ``SQLCompiler.get_order_by()``.
    '_order_to_sql': 'get_order_by',
    '_order_field_to_sql': 'get_order_by',

    # --- DDL de columna: el tipo y la alteracion ----------------------------
    # ``column_type`` (fields.py:781) devuelve ``tuple[str, str] | None`` con
    # *"the actual column type for this field, if stored as a column"*. Django:
    # ``Field.db_type(connection)``.
    'column_type': 'db_type',
    '_column_type': 'db_type',
    # ``update_db_column`` (fields.py:1130) y ``update_db_notnull``
    # (fields.py:1148, *"Add or remove the NOT NULL constraint"*) alteran una
    # columna que ya existe; ``_convert_db_column`` (fields_textual.py:64)
    # cambia su tipo. Las tres pasan en Django por
    # ``BaseDatabaseSchemaEditor.alter_field``, que compara el campo viejo con
    # el nuevo y emite el ALTER.
    'update_db_column': 'alter_field',
    'update_db_notnull': 'alter_field',
    '_convert_db_column': 'alter_field',
    # ``_add_sql_constraints`` (models.py:3262) aplica los objetos de tabla del
    # modelo a la base. Django: ``BaseDatabaseSchemaEditor.add_constraint``.
    '_add_sql_constraints': 'add_constraint',

    # --- Protocolo de descriptor: el campo se liga a su clase ---------------
    # ``setup_nonrelated(self, model)`` (fields_relational.py:91) completa el
    # campo contra su modelo. Django hace ese trabajo en
    # ``Field.contribute_to_class(cls, name)``, en la creacion de la clase.
    # Divergencia de MOMENTO, no de mecanismo — y el destino resulta generico
    # (tres paquetes instalados lo declaran), asi que la fila lo deja en
    # ``nombre_generico``: el mapa no lava un nombre generico.
    'setup_nonrelated': 'contribute_to_class',

    # La familia del setup en dos fases NO se mapea. ``prepare_setup``
    # (fields.py:523) es ``self._setup_done = False`` y nada mas: Django no
    # tiene setup en dos fases, asi que no hay simbolo renombrado que nombrar.
    # Su desenlace es CONSTRUYE y su sitio es ``sin_rastro``. Mapearlo por
    # parecido de familia seria el camino barato.
}


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


def classify(symbol, stack_index, ours_index, rename=None):
    """El cubo de un simbolo, con ``ya_esta_aqui`` por delante de todo.

    Nuestro arbol gana la precedencia porque cambia el trabajo: un simbolo que
    ya escribimos no se porta ni se construye — se reubica, o se declara por
    que vive donde vive.

    La especificidad se exige **en los dos universos**, no solo en el stack:
    ``add`` lo declaran tres archivos nuestros y ninguno es el de la fuente.
    Sin esa simetria el cubo se llena de dunders y verbos genericos, y una
    cota superior contaminada se lee como inventario.

    El mapa de renombre va **despues** de nuestro arbol y **antes** de la
    busqueda por nombre propio: una fila justificada a mano nombra el simbolo
    concreto, y pesa mas que una homonimia del indice. Y se somete a la misma
    exigencia de especificidad que todo lo demas — si su destino lo declaran
    dos o mas paquetes, el resultado es ``nombre_generico``, no
    ``trae_renombrado``. Una fila muerta (destino ausente del indice) no mueve
    nada: el simbolo cae por la via normal.
    """
    rename = STACK_RENAME if rename is None else rename
    ours = ours_index.get(symbol)
    if ours:
        return 'ya_esta_aqui' if len(ours) == 1 else 'nombre_generico'
    target = rename.get(symbol)
    if target:
        packages = stack_index.get(target)
        if packages:
            return ('trae_renombrado' if len(packages) == 1
                    else 'nombre_generico')
    packages = stack_index.get(symbol)
    if not packages:
        return 'sin_rastro'
    return 'trae_candidato' if len(packages) == 1 else 'nombre_generico'


def dead_rename_entries(stack_index, rename=None):
    """Las filas del mapa cuyo destino NO declara el stack.

    Es el control que puede fallar. Sin este listado, una fila que apunta a un
    simbolo retirado deja de mover su cubo y nadie se entera: el conteo baja un
    punto y se lee como si el mapa siguiera entero — un verde que no distingue
    «no aplica» de «el instrumento dejo de ver».
    """
    rename = STACK_RENAME if rename is None else rename
    return sorted((source, target) for source, target in rename.items()
                  if target not in stack_index)


def evidence(symbol, stack_index, ours_index, rename=None):
    """Las rutas que sostienen el cubo de ``symbol``, vengan de donde vengan.

    ``nombre_generico`` lo puede producir CUALQUIERA de los dos universos —dos
    paquetes del stack, o dos archivos nuestros—, asi que leer la evidencia
    solo del stack revienta con ``KeyError`` sobre un generico nuestro. Ocurrio
    al correrlo: ``_read_group_select``, declarado en dos addons y en ningun
    paquete instalado.

    Un simbolo renombrado apunta al DESTINO: sin eso el detalle diria
    ``trae_renombrado`` sin decir contra que, que es un cubo sin evidencia.
    """
    rename = STACK_RENAME if rename is None else rename
    ours = sorted(ours_index.get(symbol, ()))
    if not ours:
        target = rename.get(symbol)
        if target and target in stack_index:
            return sorted({path_str
                           for paths in stack_index[target].values()
                           for path_str in paths})
    stack = sorted({path_str for paths in stack_index.get(symbol, {}).values()
                    for path_str in paths})
    return ours + stack


@dataclasses.dataclass
class Total:
    """El agregado, siempre con su universo al lado."""

    universe: int
    by_bucket: dict


def summary(symbols, stack_index, ours_index, rename=None):
    """Reparte ``symbols`` en los cubos y publica su denominador."""
    counts = dict.fromkeys(BUCKETS, 0)
    for symbol in symbols:
        counts[classify(symbol, stack_index, ours_index, rename)] += 1
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

    by_file = absent_symbols(args.root)
    all_symbols = sorted({s for names in by_file.values() for s in names})
    stack = index_declarations(stack_roots())
    ours = our_declarations_outside(args.root)

    total = summary(all_symbols, stack, ours)
    print(f'=== ausentes de odoo/{args.root}: en que universo vive su nombre ===\n')
    for bucket in BUCKETS:
        n = total.by_bucket[bucket]
        pct = 100.0 * n / total.universe if total.universe else 0.0
        print(f'{bucket:<18} {n:>5}  ({pct:5.1f} %)')
    print(f'\nuniverso: {total.universe} simbolo(s) ausente(s) distintos '
          f'en {len(by_file)} archivo(s) de la referencia')
    print(f'indice del stack: {len(stack)} nombre(s) declarado(s); '
          f'nuestro arbol fuera de src/{args.root}: {len(ours)}')

    dead = dead_rename_entries(stack)
    print(f'mapa de renombre: {len(STACK_RENAME)} fila(s), '
          f'{len(dead)} muerta(s)')
    for source, target in dead:
        print(f'  FILA MUERTA  {source} -> {target}: el stack no lo declara; '
              'la fila no mueve de cubo a su simbolo')

    if args.detalle:
        print()
        for symbol in all_symbols:
            bucket = classify(symbol, stack, ours)
            target = STACK_RENAME.get(symbol)
            label = f'{symbol} -> {target}' if target else symbol
            where = ', '.join(evidence(symbol, stack, ours)[:3])
            print(f'{bucket:<18} {label:<58} {where}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
