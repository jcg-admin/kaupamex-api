#!/usr/bin/env python3
"""Censo de ``odoo/orm/`` — que simbolo de la referencia falta en ``src/orm/``.

Mide, por archivo, los **simbolos de nivel superior** que la referencia declara
y este arbol no: clases, funciones y constantes de modulo. Es la entrada de la
tarea #209, que exige un veredicto por simbolo — ``TRAE`` (el stack ya lo trae
instalado), ``CONSTRUYE`` (las primitivas estan y no hace falta dependencia de
fuera) o ``EXCLUIDO`` con su razon medida.

El guion es el **mecanismo**; el registro de veredictos vive en ``docs``
(``calibration-verified-numbers.md``: una cifra que vive en codigo no se
transcribe a prosa). Por eso aqui no hay ninguna tabla de resultados: se
publican al correr.

Metrica
-------
Nombres ligados en el cuerpo del modulo, por AST: ``ClassDef``,
``FunctionDef``, ``AsyncFunctionDef`` y el destino de un ``Assign`` simple.

Ciega a
-------
- **Metodos dentro de una clase.** Un ``Field`` con la mitad de sus metodos
  cuenta como presente. Para eso esta ``check_porte_completo``.
- **El reparto entre archivos.** Este arbol declara algunos simbolos en un
  archivo distinto del de la fuente, asi que la comparacion por archivo
  sobreestima; ``--global`` la corrige buscando el nombre en toda la root.
- **El renombre.** Un simbolo portado con otro nombre se cuenta como ausente.

Uso
---
    python3 scripts/census_orm_reference.py            # por archivo
    python3 scripts/census_orm_reference.py --global   # busca en toda la raiz
    python3 scripts/census_orm_reference.py --file fields.py   # el detalle
"""
import argparse
import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reference_roots  # noqa: E402  — hermano, no import perezoso

#: La raiz espejada que este censo mide. La fuente la llama ``odoo/orm``.
REFERENCE_SUBPATH = ('odoo', 'orm')
OUR_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'src' / 'orm'


def top_level_symbols(path):
    """Los nombres que el modulo liga en su cuerpo, con su linea."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError):
        return {}
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            found[node.name] = node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.lineno
    return found


def reference_root():
    """La raiz ``odoo/orm`` del arbol que gobierna, por alias."""
    orm = pathlib.Path(reference_roots.tree('odoo19c')).joinpath(
        *REFERENCE_SUBPATH)
    if not orm.is_dir():
        # Rehusa con codigo propio en vez de emitir 0: un cero aqui no
        # distingue "no falta nada" de "no pude medir" — el sub-patron D de
        # metrica-decide-la-conclusion.md.
        raise SystemExit(
            f'ERROR — no existe {orm}. La root de la referencia se declara en '
            f'scripts/reference_roots.py. NO se emite un conteo: un 0 aqui '
            f'seria un verde falso.')
    return orm


def our_symbols_by_file():
    """Lo declarado en cada archivo nuestro, y el indice de toda la raiz."""
    per_file, everywhere = {}, {}
    for path in sorted(OUR_ROOT.glob('*.py')):
        symbols = top_level_symbols(path)
        per_file[path.name] = symbols
        for name in symbols:
            everywhere.setdefault(name, path.name)
    return per_file, everywhere


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--global', dest='use_global', action='store_true',
                        help='busca el simbolo en toda src/orm, no solo en el '
                             'archivo homonimo')
    parser.add_argument('--file', help='el detalle simbolo a simbolo de uno')
    args = parser.parse_args()

    root = reference_root()
    per_file, everywhere = our_symbols_by_file()

    if args.file:
        reference = top_level_symbols(root / args.file)
        if not reference:
            raise SystemExit(f'ERROR — {args.file} no declara simbolos de '
                             f'nivel superior, o no existe en la referencia.')
        print(f'=== {args.file} — {len(reference)} simbolos de nivel superior')
        for name, line in sorted(reference.items(), key=lambda kv: kv[1]):
            home = everywhere.get(name)
            where = f'AQUI en {home}' if home else 'AUSENTE'
            print(f'  :{line:<6} {name:34} {where}')
        return 0

    print(f'{"archivo":26} {"ref":>5} {"aqui":>5} {"faltan":>7}  ausentes')
    print('-' * 96)
    total_reference = total_missing = 0
    for reference_file in sorted(root.glob('*.py')):
        reference = top_level_symbols(reference_file)
        ours = per_file.get(reference_file.name, {})
        if args.use_global:
            missing = sorted(n for n in reference if n not in everywhere)
        else:
            missing = sorted(set(reference) - set(ours))
        total_reference += len(reference)
        total_missing += len(missing)
        absent = '  [ARCHIVO AUSENTE]' if reference_file.name not in per_file else ''
        print(f'{reference_file.name:26} {len(reference):5} {len(ours):5} '
              f'{len(missing):7}  {", ".join(missing[:4])}{absent}')
    print('-' * 96)
    modo = 'toda la root' if args.use_global else 'archivo por archivo'
    print(f'{"TOTAL":26} {total_reference:5} {"":5} {total_missing:7}  '
          f'(universo: {total_reference} simbolos; modo: {modo})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
