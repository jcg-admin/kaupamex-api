#!/usr/bin/env python3
"""Censo del contrato de ``Field`` — que declara la referencia y que hay aqui.

``odoo19c: odoo/orm/fields.py`` declara ``Field`` como la clase base de la que
cuelga todo campo del ORM. Este arbol no la tiene: sus campos son alias de los
de Django (``Integer = models.IntegerField``), asi que la base real es
``django.db.models.Field``.

Antes de instalar el contrato de la fuente sobre esa base hay que medir cuatro
cosas, y ninguna se puede suponer:

1. **Que declara la fuente** — atributos de clase y metodos de ``Field``.
2. **Que colisiona** con lo que ``django.db.models.Field`` ya trae. Un simbolo
   que colisiona es de Django y se respeta; instalarlo encima romperia el ORM
   anfitrion.
3. **Que fija una instancia** de Django en su ``__init__``. Un default de clase
   que la instancia siempre pisa nunca se consulta: declararlo es inocuo pero
   no aporta. Uno que la instancia NO fija queda vivo, y ese si gobierna.
4. **Que nombre se ASIGNA** en algun sitio —de este arbol o de Django—. Un
   nombre que alguien asigna no puede portarse como ``property`` de solo
   lectura: la asignacion levantaria ``AttributeError``. Tiene que ser un
   atributo llano que la instancia pise.

La cuarta es la que no es obvia y la que decide la forma del porte. Sin ella,
la eleccion entre ``property`` y atributo llano se haria a ojo.

Uso::

    uv run python scripts/census_field_contract.py            # las cuatro
    uv run python scripts/census_field_contract.py --ausentes # solo el 1 vs src
"""
import argparse
import ast
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reference_roots  # noqa: E402

import django  # noqa: E402
from django.conf import settings  # noqa: E402

#: La path de la clase dentro del arbol de la referencia.
REFERENCE_SUBPATH = ('odoo', 'orm', 'fields.py')

#: El nombre de la clase que se censa.
CLASS_NAME = 'Field'

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Donde vive el paquete de Django instalado — el que de verdad corre, no el
#: que declare ``pyproject.toml``.
DJANGO_MODELS = REPO / '.venv/lib/python3.12/site-packages/django/db/models'


def reference_class():
    """El ``ast.ClassDef`` de ``Field`` en la referencia."""
    path = pathlib.Path(reference_roots.tree('odoo19c')).joinpath(*REFERENCE_SUBPATH)
    if not path.is_file():
        # Rehusa con codigo propio en vez de emitir un censo vacio: un cero
        # aqui no distingue "no falta nada" de "no pude medir".
        raise SystemExit(
            f'ERROR — la referencia no esta en {path}. No se emite censo: '
            'un 0 sin fuente seria un verde falso.')
    return next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.ClassDef) and n.name == CLASS_NAME)


def declared_symbols(node):
    """Los atributos de clase y los metodos que el cuerpo declara, con su linea."""
    attrs, methods = [], []
    for child in node.body:
        if isinstance(child, ast.Assign):
            attrs += [(t.id, child.lineno) for t in child.targets
                      if isinstance(t, ast.Name)]
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            attrs.append((child.target.id, child.lineno))
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append((child.name, child.lineno))
    return attrs, methods


def files_mentioning(name, root):
    """Cuantos archivos de ``root`` nombran ``name`` con limite de palabra.

    El limite importa: ``setup`` sin el aparece en cientos de contextos que no
    son el metodo, y el censo publicaria presente lo que falta.
    """
    pat = re.compile(r'\b' + re.escape(name) + r'\b')
    return sum(1 for p in root.rglob('*.py')
               if pat.search(p.read_text(errors='ignore')))


def assignments_of(name, root):
    """Cuantas veces se ASIGNA ``.name =`` bajo ``root``."""
    pat = re.compile(r'\.' + re.escape(name) + r'\s*=(?!=)')
    return sum(len(pat.findall(p.read_text(errors='ignore')))
               for p in root.rglob('*.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ausentes', action='store_true',
                        help='solo los simbolos que no aparecen en src/')
    args = parser.parse_args()

    settings.configure(INSTALLED_APPS=[], DATABASES={})
    django.setup()
    from django.db import models

    node = reference_class()
    attrs, methods = declared_symbols(node)
    src = REPO / 'src'

    print(f'=== {CLASS_NAME} — lineas {node.lineno}-{node.end_lineno} de la referencia ===')
    print(f'atributos {len(attrs)} · metodos {len(methods)} · total {len(attrs) + len(methods)}')

    print('\n--- 1. AUSENTES en src/ (limite de palabra) ---')
    for etiqueta, grupo in (('atributo', attrs), ('metodo', methods)):
        missing = [(n, l) for n, l in grupo if not files_mentioning(n, src)]
        print(f'  {etiqueta}s ausentes: {len(missing)} de {len(grupo)}')
        for n, l in missing:
            print(f'    :{l:<5} {n}')
    if args.ausentes:
        return

    print('\n--- 2. COLISIONES con django.db.models.Field ---')
    choca = [(n, l, k) for k, grupo in (('atributo', attrs), ('metodo', methods))
             for n, l in grupo if hasattr(models.Field, n)]
    print(f'  {len(choca)} de {len(attrs) + len(methods)}')
    for n, l, k in choca:
        print(f'    :{l:<5} {k:<9} {n}')

    print('\n--- 3. ATRIBUTOS que una instancia de Django YA fija ---')
    probe = models.CharField(max_length=8)
    fijados = [n for n, _ in attrs if n in vars(probe)]
    print(f'  {len(fijados)} de {len(attrs)}: {sorted(fijados)}')
    print(f'  -> los otros {len(attrs) - len(fijados)} quedan como default de clase VIVO')

    print('\n--- 4. NOMBRES QUE SE ASIGNAN (no pueden ser property) ---')
    for etiqueta, root in (('src', src), ('django', DJANGO_MODELS)):
        if not root.is_dir():
            print(f'  {etiqueta}: root ausente en {root} — no se mide, no se emite 0')
            continue
        print(f'  {etiqueta}:')
        for n, _ in attrs:
            times = assignments_of(n, root)
            if times:
                print(f'    {times:5}  {n}')


if __name__ == '__main__':
    main()
