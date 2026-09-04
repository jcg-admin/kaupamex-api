#!/usr/bin/env python3
"""Censo de los 20 tipos de campo — la referencia contra Django, por CONDUCTA.

El defecto que este guion existe para cerrar
=============================================

``orm/fields.py`` declara ``DJANGO_TYPE_TO_TTYPE``, un mapa de nombres::

    'ManyToManyField': 'many2many'

y de ese mapa se concluyo, sin medirlo, que el mecanismo era equivalente. Es
el sub-patron **C** de ``metrica-decide-la-conclusion.md``: el instrumento
mide la **forma** —como se llama el tipo— y la conclusion es sobre el
**fondo** —que hace—. Una fila del mapa dice que los dos tipos se llaman uno
como el otro; no dice que hagan lo mismo.

Medido sobre ``Many2many`` antes de escribir este guion: la referencia lo
declara sobre ``_RelationalMulti`` y ``_Relational``, con ``domain``,
``context``, ``bypass_search_access``, ``check_company``, ``ondelete``,
``relation``, ``column1``, ``column2``, ``_explicit`` y el protocolo de
escritura por ``Command`` (``write_real``, ``write_new``, ``write_batch``).
``django.db.models.ManyToManyField`` no trae ninguno de esos.

Que mide
========

Para cada tipo exported en ``orm/fields.__all__``:

1. **La referencia** — la clase que lo declara en ``odoo/orm/fields_*.py``,
   con su cadena de herencia dentro de la referencia, y la union de los
   atributos y metodos que esa cadena declara. Es el contrato completo, no el
   de la hoja: ``Many2many`` hereda de ``_RelationalMulti`` lo que la hoja no
   repite.
2. **Django** — la clase a la que este arbol lo liga, y que de ese contrato
   ya answered (por ``hasattr``, incluida su propia herencia).
3. **La diferencia** — lo que hay que construir encima de Django.

*Metrica:* nombres declarados en el cuerpo de cada clase de la referencia
(por AST), contra ``hasattr`` sobre la clase de Django instalada.
*Ciega a:* un symbol que Django **tenga con otro name** —``verbose_name``
frente a ``string``— y a uno que tenga con el mismo name y **otra
semantica**. La primera ceguera la cierra el mapa de alias de
``orm/fields.py``; la segunda solo la cierra leer los dos cuerpos, y por eso
el veredicto por tipo se escribe a mano sobre esta salida, no se deriva de
ella.

Uso::

    uv run python scripts/census_field_types.py            # los 20
    uv run python scripts/census_field_types.py Many2many  # uno
"""
import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reference_roots  # noqa: E402

import os  # noqa: E402

import django  # noqa: E402

#: Los archivos de la referencia que declaran classes de campo.
REFERENCE_FILES = (
    'fields.py', 'fields_binary.py', 'fields_misc.py', 'fields_numeric.py',
    'fields_properties.py', 'fields_reference.py', 'fields_relational.py',
    'fields_selection.py', 'fields_temporal.py', 'fields_textual.py',
)

#: Los alias que este arbol ya reconoce entre un nombre de la fuente y su
#: contraparte de Django. Sin esta tabla el censo publicaria como ausente lo
#: que existe con otro nombre — la primera de las dos cegueras del docstring.
KNOWN_ALIASES = {
    'string': 'verbose_name',
    'help': 'help_text',
    'index': 'db_index',
    'comodel_name': 'related_model',
    'relational': 'is_relation',
    'ondelete': 'remote_field',       # Django lo guarda en el remote_field
    'relation': 'db_table',           # la tabla puente del M2M
    'column1': 'm2m_column_name',
    'column2': 'm2m_reverse_name',
    'domain': 'limit_choices_to',
}


def reference_classes():
    """``{nombre_de_clase: (source_file, node)}`` de toda la referencia de campos."""
    root = pathlib.Path(reference_roots.tree('odoo19c')) / 'odoo' / 'orm'
    if not root.is_dir():
        raise SystemExit(
            f'ERROR — la referencia no esta en {root}. No se emite censo.')
    found = {}
    for name in REFERENCE_FILES:
        path = root / name
        if not path.is_file():
            continue
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.ClassDef):
                found[node.name] = (name, node)
    return found


def declared_by(node):
    """Atributos y metodos que el cuerpo de esta clase declara."""
    attrs, methods = set(), set()
    for child in node.body:
        if isinstance(child, ast.Assign):
            attrs |= {t.id for t in child.targets if isinstance(t, ast.Name)}
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            attrs.add(child.target.id)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.add(child.name)
    return attrs, methods


def contract_of(name, classes, seen=None):
    """El contrato COMPLETO de un tipo: lo suyo mas lo de sus bases.

    La hoja no repite lo que hereda — ``Many2many`` no vuelve a declarar
    ``domain``, lo trae de ``_Relational``—, asi que medir solo la hoja
    publicaria un contrato mucho menor del real.
    """
    seen = seen if seen is not None else set()
    if name in seen or name not in classes:
        return set(), set(), []
    seen.add(name)
    _, node = classes[name]
    attrs, methods = declared_by(node)
    chain = [name]
    for base in node.bases:
        base_name = base.id if isinstance(base, ast.Name) else getattr(base, 'attr', None)
        if not base_name:
            continue
        b_attrs, b_methods, b_cadena = contract_of(base_name, classes, seen)
        attrs |= b_attrs
        methods |= b_methods
        chain += b_cadena
    return attrs, methods, chain


def django_answers(symbol, django_class):
    """¿La clase de Django responde a este simbolo, por su nombre o su alias?"""
    if hasattr(django_class, symbol):
        return symbol
    alias = KNOWN_ALIASES.get(symbol)
    if alias and hasattr(django_class, alias):
        return alias
    return None


def main():
    # Los settings REALES, no un ``configure`` pelado: ``fields_reference``
    # importa ``GenericForeignKey``, que arrastra ``ContentType``, y un
    # registro de apps vacío lo rechaza con ``RuntimeError``. Medirlo con un
    # arranque falso mediría otro árbol.
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'src'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()

    import orm.fields as nuestro

    requested = sys.argv[1:]
    classes = reference_classes()
    total_missing = 0

    for exported in nuestro.__all__:
        if requested and exported not in requested:
            continue
        django_class = getattr(nuestro, exported, None)
        if django_class is None:
            # Un exported que el modulo declara en ``__all__`` y no liga a
            # ninguna clase: es un hueco del arbol, no de la referencia. Se
            # nombra en vez de reventar — un censo que muere en la primera
            # anomalia deja sin medir todo lo que venia detras.
            print(f'=== {exported} — NO ligado a ninguna clase en '
                  f'orm.fields; hueco del arbol ===\n')
            continue
        if exported not in classes:
            print(f'=== {exported} — la referencia NO declara una clase con '
                  f'este name; se mide aparte ===\n')
            continue
        source_file, _ = classes[exported]
        attrs, methods, chain = contract_of(exported, classes)
        contract = sorted(attrs | methods)
        missing = [s for s in contract if django_answers(s, django_class) is None]
        answered = [(s, django_answers(s, django_class)) for s in contract
                    if django_answers(s, django_class) is not None]
        total_missing += len(missing)

        django_name = getattr(django_class, '__name__', repr(django_class))
        print(f'=== {exported} → {django_name} ({source_file}) ===')
        print(f'  cadena en la referencia: {" ← ".join(chain)}')
        print(f'  contrato: {len(contract)} simbolos '
              f'({len(attrs)} atributos + {len(methods)} metodos)')
        print(f'  Django YA responde: {len(answered)}')
        aliased = [(s, a) for s, a in answered if s != a]
        if aliased:
            print(f'    por alias ({len(aliased)}): '
                  + ', '.join(f'{s}→{a}' for s, a in aliased))
        print(f'  hay que CONSTRUIR: {len(missing)}')
        for s in missing:
            print(f'    {s}')
        print()

    print(f'### TOTAL a construir sobre Django: {total_missing} simbolos ###')


if __name__ == '__main__':
    main()
