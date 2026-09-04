"""Censo de la raiz espejada ``src/orm`` frente a ``odoo/orm``.

Responde una pregunta que el arbol no sabia contestar: **de los simbolos que
la referencia declara en ``odoo/orm/``, cuales estan aqui, cuales viven en
otro archivo del que la fuente les asigna, y cuales faltan.**

Por que no vale ninguno de los dos censos que ya se corrian
============================================================

``check_porte_completo`` mide por ``Clase.metodo`` y esta cableado a
``addons/<x>/models``: sobre esta raiz publicaria ``models.py 0/200``, porque
aqui ``BaseModel`` **no es una clase** — sus metodos se declaran como
funciones de modulo y mixins que ``extend_model`` cuelga. Es la ceguera
estructural que :ref:`h-api-569` ya registro, y su cierre es la tarea #52.

Un ``grep`` por nombre desnudo sobre la raiz entera comete el error opuesto:
absuelve un simbolo que existe **en otro archivo**, que es exactamente la
divergencia de sitio de :ref:`h-api-578`. Su cifra es una cota superior del
porte, no el porte.

El alcance de resolucion es **el archivo**, la misma decision que
``file_symbols`` de ``check_porte_completo`` tomo tras medir que el alcance
por addon fabricaba once coincidencias falsas de dieciocho
(:ref:`h-api-356`). Lo que aparece en otro archivo de la raiz no se cuenta
como presente: se publica en su propio cubo, ``misplaced``, porque es trabajo
de reubicacion y no de porte, y sumarlos vuelve a esconder la diferencia.

Los cinco estados que distingue
================================

=================  =====================================================
``present``        el simbolo se declara en el archivo que le
                   corresponde — como metodo, como funcion de modulo, o
                   instalado por ``extend_model``
``misplaced``      existe en la raiz, en OTRO archivo. Divergencia de
                   sitio, no porte
``dissolved``      una CLASE de la fuente que aqui no existe **y cuyos
                   miembros si llegaron**. Divergencia de forma: este
                   arbol declara los metodos de ``BaseModel`` como
                   funciones de modulo y mixins, no dentro de una clase
``missing_classes`` una clase ausente a la que ademas le falta algun
                   miembro — eso no es forma, es porte sin hacer
``missing``        un simbolo que no es clase y no esta en ninguna parte
``file_missing``   el archivo entero no tiene contraparte
=================  =====================================================

El quinto cubo es el que el instrumento destapo al correrse: ``BaseModel``
**la clase** tambien es un simbolo de la fuente, y aqui no existe por
diseno. Contarla como ausente inflaria la deuda con algo que ya se decidio;
absolverla siempre convertiria el cubo en una amnistia automatica. Por eso
la condicion es que **todos** sus miembros hayan aterrizado: una clase con
un miembro ausente sigue siendo porte pendiente.

Y el eje inverso, que ningun gate por pares puede ver: los archivos
**nuestros** sin contraparte en la fuente, que ``ours_without_counterpart``
publica aparte.
"""
import argparse
import ast
import dataclasses
import pathlib
import sys

#: Los kwargs de ``extend_model`` cuyas claves son simbolos instalados.
INSTALLER_KWARGS = ('campos', 'metodos', 'propiedades', 'overrides')

#: Las llamadas que instalan simbolos sobre una clase de otro sitio.
INSTALLERS = ('extend_model', 'install_class_attribute_overrides')


def _parse(path):
    """El AST del archivo, o ``None`` si no parsea."""
    try:
        return ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return None


def reference_symbols(path):
    """Los simbolos que la fuente declara en un archivo, en orden de lectura.

    Cuenta clases, funciones de modulo y metodos a cualquier profundidad —
    la misma poblacion sobre la que se publico el 302/644, para que las dos
    cifras sean comparables.
    """
    tree = _parse(path)
    if tree is None:
        return []
    seen, out = set(), []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name not in seen:
                seen.add(node.name)
                out.append(node.name)
    return out


def declared_symbols(path):
    """Los simbolos que UN archivo nuestro declara o instala.

    Tres vias, y las tres cuentan porque las tres dejan el simbolo utilizable:
    la declaracion directa (``def`` / ``class``), y las claves de los dicts
    literales que ``extend_model`` recibe. Un dict cualquiera **no** absuelve:
    la clave sale del nodo de la llamada, no de cualquier literal del archivo.
    """
    tree = _parse(path)
    if tree is None:
        return set()
    out = {node.name for node in ast.walk(tree)
           if isinstance(node, (ast.ClassDef, ast.FunctionDef,
                                ast.AsyncFunctionDef))}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = (node.func.attr if isinstance(node.func, ast.Attribute)
                else getattr(node.func, 'id', ''))
        if name not in INSTALLERS:
            continue
        for kw in node.keywords:
            if kw.arg in INSTALLER_KWARGS and isinstance(kw.value, ast.Dict):
                out |= {k.value for k in kw.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return out


def class_members(path):
    """``{clase: {miembros directos}}`` de un archivo de la referencia.

    Es lo que decide si una clase ausente aqui es **forma** o es **porte sin
    hacer**: sin la lista de sus miembros no se puede distinguir una clase que
    este arbol disolvio a proposito de una que nadie porto.
    """
    tree = _parse(path)
    if tree is None:
        return {}
    return {
        node.name: {
            n.name for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }


@dataclasses.dataclass
class Row:
    """El veredicto de UN archivo de la referencia."""
    name: str
    file_missing: bool
    reference: list
    present: set
    missing: list
    misplaced: dict
    dissolved: list
    missing_classes: list


@dataclasses.dataclass
class Total:
    """El agregado, con su poblacion — nunca un conteo suelto."""
    files: int
    files_missing: int
    reference_symbols: int
    present: int
    missing: int
    misplaced: int
    dissolved: int


def census(ref_dir, mine_dir):
    """``{archivo: Row}`` — un veredicto por archivo de la referencia."""
    ref_dir, mine_dir = pathlib.Path(ref_dir), pathlib.Path(mine_dir)
    # El indice de la raiz entera se construye UNA vez: es lo que permite
    # separar «no esta» de «esta en otro archivo» sin recorrer N veces.
    elsewhere = {}
    for path in sorted(mine_dir.glob('*.py')):
        for symbol in declared_symbols(path):
            elsewhere.setdefault(symbol, path.name)

    rows = {}
    for ref_py in sorted(ref_dir.glob('*.py')):
        if ref_py.name == '__init__.py':
            continue
        symbols = reference_symbols(ref_py)
        classes = class_members(ref_py)
        mine_py = mine_dir / ref_py.name
        here = declared_symbols(mine_py) if mine_py.exists() else set()
        present = {s for s in symbols if s in here}
        rest = [s for s in symbols if s not in here]
        misplaced = {s: elsewhere[s] for s in rest if s in elsewhere}

        # Lo que queda sin contraparte se reparte en tres, no en uno: una
        # clase ausente cuyos miembros SI llegaron es divergencia de forma;
        # una a la que le falta alguno es porte pendiente; y lo que no es
        # clase es, sin mas, ausente.
        landed = here | set(elsewhere)
        dissolved, missing_classes, missing = [], [], []
        for symbol in rest:
            if symbol in misplaced:
                continue
            if symbol in classes:
                members = classes[symbol]
                if members and members <= landed:
                    dissolved.append(symbol)
                else:
                    missing_classes.append(symbol)
            else:
                missing.append(symbol)

        rows[ref_py.name] = Row(
            name=ref_py.name,
            file_missing=not mine_py.exists(),
            reference=symbols,
            present=present,
            missing=missing,
            misplaced=misplaced,
            dissolved=dissolved,
            missing_classes=missing_classes,
        )
    return rows


def ours_without_counterpart(ref_dir, mine_dir):
    """Los archivos nuestros que la referencia no declara.

    Es el eje que ``check_porte_completo`` no puede ver por construccion: sin
    contraparte no hay con que comparar (:ref:`h-api-569`). Cada uno necesita
    su veredicto — mecanismo propio declarado, o archivo en sitio divergente.
    """
    ref_dir, mine_dir = pathlib.Path(ref_dir), pathlib.Path(mine_dir)
    reference = {p.name for p in ref_dir.glob('*.py')}
    return sorted(p.name for p in mine_dir.glob('*.py')
                  if p.name not in reference and p.name != '__init__.py')


def summary(rows):
    """El agregado de un censo, con su denominador."""
    return Total(
        files=len(rows),
        files_missing=sum(1 for r in rows.values() if r.file_missing),
        reference_symbols=sum(len(r.reference) for r in rows.values()),
        present=sum(len(r.present) for r in rows.values()),
        # Una clase ausente sin disolver cuenta como ausente en el agregado,
        # aunque en la fila viva en su propio cubo: el denominador del porte
        # son los simbolos de la fuente, y ella es uno.
        missing=sum(len(r.missing) + len(r.missing_classes)
                    for r in rows.values()),
        misplaced=sum(len(r.misplaced) for r in rows.values()),
        dissolved=sum(len(r.dissolved) for r in rows.values()),
    )


def _roots(root_name):
    """Las dos raices espejadas, resueltas por ``reference_roots``."""
    sys.path.insert(0, 'scripts')
    import reference_roots  # noqa: PLC0415 — el guion vive fuera del paquete

    ref = reference_roots.tree('odoo19c') / 'odoo' / root_name
    return ref, pathlib.Path('src') / root_name


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='orm',
                        help='la raiz espejada a medir (orm, tools, ...)')
    parser.add_argument('--detalle', action='store_true',
                        help='listar los simbolos ausentes de cada archivo')
    args = parser.parse_args(argv)

    ref, mine = _roots(args.root)
    if not ref.is_dir():
        print(f'AVISO: no esta la raiz de referencia en {ref}; '
              'sin ella este censo no puede medir nada.')
        return 2

    rows = census(ref, mine)
    total = summary(rows)

    print(f'=== odoo/{args.root} <-> src/{args.root} ===\n')
    print(f'{"archivo":<28} {"ref":>5} {"aqui":>5} {"otro":>5} '
          f'{"disue":>6} {"falta":>6}')
    for row in rows.values():
        marca = '  (SIN CONTRAPARTE)' if row.file_missing else ''
        faltan = len(row.missing) + len(row.missing_classes)
        print(f'{row.name:<28} {len(row.reference):>5} {len(row.present):>5} '
              f'{len(row.misplaced):>5} {len(row.dissolved):>6} '
              f'{faltan:>6}{marca}')
        if args.detalle and row.missing:
            print(f'    ausentes: {", ".join(row.missing)}')
        if args.detalle and row.missing_classes:
            print('    clases sin portar: ' + ", ".join(row.missing_classes))
        if args.detalle and row.dissolved:
            print('    clases disueltas: ' + ", ".join(row.dissolved))
        if args.detalle and row.misplaced:
            print('    en otro archivo: ' + ", ".join(
                f'{s} -> {f}' for s, f in sorted(row.misplaced.items())))

    pct = 100 * total.present / total.reference_symbols if total.reference_symbols else 0
    print(f'\npresentes en su archivo: {total.present} de '
          f'{total.reference_symbols} ({pct:.1f} %) · '
          f'en otro archivo: {total.misplaced} · '
          f'clases disueltas: {total.dissolved} · '
          f'ausentes: {total.missing}')
    print(f'(alcance medido: {total.files} archivos de la referencia, '
          f'{total.files_missing} sin contraparte)')

    sobran = ours_without_counterpart(ref, mine)
    print(f'nuestros sin contraparte en la fuente: {len(sobran)}'
          + (f' — {", ".join(sobran)}' if sobran else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
