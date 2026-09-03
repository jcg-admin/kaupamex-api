"""Reparte los ocho simbolos del eje de campos de ``Registry`` en tres cubos.

Pregunta que responde, y es la del ejecutor: para cada simbolo de la
referencia, **el stack lo trae hecho** —hay un simbolo instalado y basta
llamarlo— o **el stack tiene con que construirlo** —no hay simbolo hecho,
pero las primitivas estan y no hace falta ninguna dependencia de fuera—.

La poblacion son los ocho que ``odoo19c: odoo/orm/registry.py`` declara entre
``field_inverses`` (``:506``) e ``is_modifying_relations`` (``:670``). No es
``Registry`` entero: los otros cuatro tramos de la tarea **#342** tienen su
propia medicion.

El instrumento no lee prosa: resuelve cada dotted path por ``importlib`` mas
``getattr`` encadenado. Un nombre que no resuelve sale nombrado, y el simbolo
que lo pedia cae en ``BLOCKED`` — que es la unica forma de que este guion
pueda decir que no. Su control vive en ``tests/``.

*Metrica:* dotted paths que resuelven en el interprete del proyecto.
*Ciega a:* la conducta del simbolo instalado — mide que el nombre existe, no
que haga lo mismo que la referencia.
"""
import argparse
import importlib
import json
import pathlib
import sys
from dataclasses import dataclass


#: El inventario de proveedores, verbatim como lo declara el ejecutor. La
#: clave es el par (paquete, trabajo que hace); el valor queda vacio porque
#: aqui el inventario se usa como vocabulario cerrado, no como tabla de datos.
INVENTORY = {
    ('cpython', 'contencion por bytecode'): '',
    ('django', 'evaluacion y control de flujo'): '',
    ('django', 'almacen del arch por key'): '',
    ('django', 'formateo por locale'): '',
    ('django', 'recorrido del arbol a dict'): '',
    ('drf', 'contrato del endpoint'): '',
    ('lxml', 'parseo, XPath y construccion de nodos'): '',
    ('lxml', 'herencia entre vistas por XPath'): '',
    ('postgresql', 'guardar y consultar el arch'): '',
    ('gunicorn', 'servir el documento'): '',
    ('libharu', 'emitir el PDF'): '',
    ('libharu', 'leer y fusionar el PDF'): '',
    ('pypdf', 'leer y fusionar el PDF'): '',
}


@dataclass(frozen=True)
class Symbol:
    """Un simbolo de la referencia y con que se paga aqui."""

    name: str
    reference: str
    does: str
    provider: tuple
    installed: tuple
    primitives: tuple


@dataclass(frozen=True)
class Verdict:
    name: str
    kind: str
    missing: tuple


#: Los ocho del tramo. ``installed`` nombra lo que YA hace el trabajo entero;
#: ``primitives``, lo que hace falta para escribirlo. Un simbolo con
#: ``installed`` vacio no es un bloqueo: es trabajo declarado.
SYMBOLS = (
    Symbol(
        name='field_inverses',
        reference='odoo19c: odoo/orm/registry.py:506',
        does='cada lado de una relacion apunta al otro',
        provider=('django', 'recorrido del arbol a dict'),
        # La fuente lo construye con un setup_inverses por clase de campo
        # porque su ORM no guarda la vuelta. Django si: la relacion inversa
        # es un objeto propio que _meta.get_fields() publica.
        installed=(
            'django.db.models.options.Options.get_fields',
            'django.db.models.fields.reverse_related.ForeignObjectRel',
        ),
        primitives=('tools.misc.Collector.add',),
    ),
    Symbol(
        name='field_computed',
        reference='odoo19c: odoo/orm/registry.py:514',
        does='agrupa los campos que comparten metodo de calculo y avisa de tres incoherencias',
        provider=('cpython', 'contencion por bytecode'),
        # No hay nada instalado que agrupe por ``compute`` ni que emita los
        # tres avisos de consistencia: se escribe.
        installed=(),
        primitives=(
            'collections.defaultdict',
            'warnings.warn',
            'django.db.models.options.Options.get_fields',
        ),
    ),
    Symbol(
        name='get_trigger_tree',
        reference='odoo19c: odoo/orm/registry.py:552',
        does='funde los arboles de los campos que cambiaron, filtrando por select',
        provider=('cpython', 'contencion por bytecode'),
        installed=(),
        primitives=('orm.registry.TriggerTree.merge',),
    ),
    Symbol(
        name='get_dependent_fields',
        reference='odoo19c: odoo/orm/registry.py:565',
        does='recorre el arbol en profundidad y entrega los campos dependientes',
        provider=('cpython', 'contencion por bytecode'),
        installed=(),
        primitives=('orm.registry.TriggerTree.depth_first',),
    ),
    Symbol(
        name='_discard_fields',
        reference='odoo19c: odoo/orm/registry.py:573',
        does='retira los campos dados de las cinco estructuras derivadas a la vez',
        provider=('cpython', 'contencion por bytecode'),
        installed=(),
        primitives=(
            'tools.misc.Collector.discard_keys_and_values',
            'orm.registry.field_depends',
        ),
    ),
    Symbol(
        name='get_field_trigger_tree',
        reference='odoo19c: odoo/orm/registry.py:592',
        does='cierra transitivamente los disparadores de un campo en un arbol',
        provider=('cpython', 'contencion por bytecode'),
        installed=(),
        primitives=(
            'orm.registry.TriggerTree.increase',
            'tools.misc.OrderedSet',
        ),
    ),
    Symbol(
        name='_field_triggers',
        reference='odoo19c: odoo/orm/registry.py:643',
        does='invierte las dependencias declaradas en {campo: {camino: campos}}',
        provider=('cpython', 'contencion por bytecode'),
        installed=(),
        primitives=(
            'collections.defaultdict',
            'tools.misc.OrderedSet',
            'orm.fields.Field.resolve_depends',
        ),
    ),
    Symbol(
        name='is_modifying_relations',
        reference='odoo19c: odoo/orm/registry.py:669',
        does='si tocar el campo puede cambiar QUE filas dependen de el',
        provider=('django', 'recorrido del arbol a dict'),
        # La mitad que decide si un campo es relacional la trae Django en
        # is_relation; la fuente la lleva en un atributo propio del campo.
        installed=('django.db.models.fields.Field.is_relation',),
        primitives=(),
    ),
)


def resolve(path):
    """¿Existe el dotted path en este interprete?

    Prueba el prefijo mas largo que importe como modulo y baja el resto con
    ``getattr``. Asi resuelve tanto ``collections.defaultdict`` —atributo de
    un modulo— como ``tools.misc.Collector.add``, que es atributo de una clase
    dentro de un modulo.
    """
    parts = path.split('.')
    module = None
    consumed = 0
    for size in range(len(parts), 0, -1):
        try:
            module = importlib.import_module('.'.join(parts[:size]))
        except ImportError:
            continue
        consumed = size
        break
    if module is None:
        return False
    current = module
    for name in parts[consumed:]:
        try:
            current = getattr(current, name)
        except AttributeError:
            return False
    return True


def classify(symbol):
    """El cubo de un simbolo, y lo que le falta si esta bloqueado."""
    missing_installed = tuple(p for p in symbol.installed if not resolve(p))
    if symbol.installed and not missing_installed:
        missing = tuple(p for p in symbol.primitives if not resolve(p))
        if missing:
            return Verdict(symbol.name, 'BLOCKED', missing)
        return Verdict(symbol.name, 'READY', ())
    missing = tuple(p for p in symbol.primitives if not resolve(p))
    if missing:
        return Verdict(symbol.name, 'BLOCKED', missing)
    return Verdict(symbol.name, 'BUILDABLE', ())


def report():
    """El reparto, con su denominador."""
    verdicts = [classify(symbol) for symbol in SYMBOLS]
    buckets = {'READY': [], 'BUILDABLE': [], 'BLOCKED': []}
    for verdict in verdicts:
        buckets[verdict.kind].append(verdict)
    return verdicts, buckets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json', action='store_true',
                        help='emite el reparto como JSON en vez de tabla')
    parser.add_argument('--strict', action='store_true',
                        help='sale 1 si algun simbolo queda BLOCKED')
    args = parser.parse_args(argv)

    verdicts, buckets = report()
    total = len(SYMBOLS)

    if args.json:
        payload = {
            'total': total,
            'buckets': {k: [v.name for v in vs] for k, vs in buckets.items()},
            'missing': {v.name: list(v.missing) for v in verdicts if v.missing},
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        by_name = {s.name: s for s in SYMBOLS}
        print(f'Eje de campos de Registry — {total} simbolos medidos\n')
        for verdict in verdicts:
            symbol = by_name[verdict.name]
            paquete, trabajo = symbol.provider
            print(f'  {verdict.kind:<9} {verdict.name:<24} '
                  f'{paquete}/{trabajo}')
            print(f'            {symbol.reference}')
            print(f'            {symbol.does}')
            if verdict.missing:
                print(f'            AUSENTE: {", ".join(verdict.missing)}')
        print()
        for kind in ('READY', 'BUILDABLE', 'BLOCKED'):
            nombres = [v.name for v in buckets[kind]]
            print(f'{kind}: {len(nombres)} de {total} — {", ".join(nombres) or "ninguno"}')

    salida = pathlib.Path(__file__).resolve().parent / 'outputs' / 'verdicts.json'
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps(
        {'total': total,
         'buckets': {k: [v.name for v in vs] for k, vs in buckets.items()},
         'missing': {v.name: list(v.missing) for v in verdicts if v.missing}},
        indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    if args.strict and buckets['BLOCKED']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
