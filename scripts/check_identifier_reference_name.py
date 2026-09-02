#!/usr/bin/env python3
"""Ningún identificador ni nombre de archivo de la api lleva el nombre de la
referencia.

Directiva del ejecutor 2026-09-02: *«En nuestra api, ningún archivo, clase,
función o firma de función, debe de tener odoo-*»*.

El motivo es de identidad, no de estética. Este árbol **adapta** la referencia;
no la ejecuta ni la extiende. Un símbolo nuestro que lleva su nombre confunde
las dos cosas: hace pasar por prestada una pieza que es del producto, y arrastra
al lector a buscar en la referencia un símbolo que sólo existe aquí.

El caso que lo motivó lo prueba: ``campo.odoo_translate = bool(translate)``
convivía con ``models.Field.translate``, que ``orm/fields.py`` ya declaraba con
el defecto de la fuente. Eran **dos nombres para la misma cosa**, y el de la
referencia le ganaba el sitio al nuestro — que además era el fiel, porque
``translate`` es como la fuente llama al atributo
(``odoo19c: odoo/orm/fields.py:288``). Quitar el prefijo no fue rebautizar: fue
recuperar el nombre que ya existía.

Qué mide y qué NO
=================

*Métrica:* el nombre declarado de cada clase, función, parámetro y destino de
asignación —por AST— más el *stem* de cada archivo ``.py``, sobre las raíces de
código de este repo.

*Ciega a:* toda **cadena**. El alias de cita (``'odoo19c'``), el nombre de la
variable de entorno (``os.environ['ODOO19C']``) y la prosa de docstrings y
comentarios quedan fuera **a propósito**: son la forma en que este árbol
*nombra su fuente*, que es justo lo contrario del defecto. Ciega también a un
identificador que aluda a la referencia sin escribir su nombre.

Nace sin baseline: el árbol estaba en 0 al cablearlo, así que no hay deuda que
congelar. Un identificador nuevo bloquea.
"""
import argparse
import ast
import pathlib
import sys

#: El nombre de la referencia, en minúsculas. Se compara contra el
#: identificador en minúsculas, así que cubre ``ODOO19C``, ``Odoo`` y
#: ``odoo_translate`` con una sola entrada.
REFERENCE_NAME = 'odoo'

#: Las raíces de código de este repo. ``config`` entra porque los settings son
#: código de la app; ``scripts`` porque el tooling también es nuestro.
DEFAULT_ROOTS = ('src', 'tests', 'addons', 'scripts', 'config')


def declared_identifiers(tree):
    """Los identificadores que el archivo **declara**, con su línea.

    Se miran los cuatro sitios donde un nombre nace: la definición de clase o
    función, el parámetro de una firma, y el destino de una asignación —tanto
    ``nombre = …`` como ``objeto.atributo = …``. Una **lectura** no declara
    nada, así que no entra: leer ``os.environ['ODOO19C']`` es citar la fuente,
    no bautizar un símbolo propio.
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node.lineno
        elif isinstance(node, ast.arg):
            yield node.arg, node.lineno
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            yield node.id, node.lineno
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            yield node.attr, node.lineno


def offenders_in(path):
    """Los incumplidores de un archivo: su nombre y sus identificadores."""
    found = []
    if REFERENCE_NAME in path.stem.lower():
        found.append((0, path.stem, 'nombre de archivo'))
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError):
        # silent OK because un archivo que no parsea no es de este gate: lo
        # bloquea antes quien compila. Medir su nombre ya se hizo arriba.
        return found
    for name, lineno in declared_identifiers(tree):
        if REFERENCE_NAME in name.lower():
            found.append((lineno, name, 'identificador'))
    return found


def files_to_measure(paths):
    if paths:
        return [pathlib.Path(p) for p in paths if p.endswith('.py')]
    root = pathlib.Path(__file__).resolve().parent.parent
    files = []
    for name in DEFAULT_ROOTS:
        directory = root / name
        if directory.is_dir():
            files.extend(
                f for f in directory.rglob('*.py') if '__pycache__' not in f.parts)
    return sorted(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', help='archivos a medir')
    args = parser.parse_args(argv)

    files = files_to_measure(args.paths)
    offenders = []
    for path in files:
        for lineno, name, kind in offenders_in(path):
            offenders.append(f'{path}:{lineno}: {kind} «{name}»')

    if offenders:
        print(f'Identificadores con el nombre de la referencia '
              f'(directiva del ejecutor 2026-09-02):')
        for line in offenders:
            print(f'  {line}')
        print(f'\nTotal: {len(offenders)} sobre {len(files)} archivos medidos. '
              f'Renombra al término del dominio; si la fuente ya le da nombre, '
              f'ése es el que va (traducir no es rebautizar).')
        return 1

    print(f'OK: ningun identificador lleva el nombre de la referencia '
          f'({len(files)} archivos medidos).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
