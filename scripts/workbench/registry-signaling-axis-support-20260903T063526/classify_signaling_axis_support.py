"""Reparte el eje de senalizacion de ``Registry`` en los dos cubos del criterio.

**La pregunta.** De los siete simbolos que la referencia declara entre
``setup_signaling`` (``odoo19c: odoo/orm/registry.py:1036``) y ``cursor``
(``:1165``), cuales trae hechos este stack —hay un simbolo instalado y basta
llamarlo— y cuales hay que construir con sus primitivas, sin ninguna
dependencia de fuera.

**Como responde.** Cada simbolo declara dos listas de rutas punteadas: lo que
ya hace el trabajo (``installed``) y lo que hace falta para construirlo
(``primitives``). El instrumento las resuelve por ``importlib`` mas una cadena
de ``getattr`` y reparte:

- **READY** — todo ``installed`` resuelve: el porte es una llamada.
- **BUILDABLE** — nada ``installed`` resuelve pero todas las ``primitives`` si.
- **BLOCKED** — alguna ``primitive`` no resuelve, y el veredicto la nombra.

El control que discrimina no vive aqui sino en el suite y en
``neutralize_and_measure.sh``: retirando ``src`` del ``PYTHONPATH``, los
simbolos que se apoyan en nuestro propio arbol pasan a BLOCKED. Un
clasificador que devolviera BUILDABLE siempre daria el mismo reparto en los
dos casos.
"""
import argparse
import importlib
import json
import sys
from dataclasses import dataclass, field

#: El inventario del ejecutor, verbatim: los origenes con los que se paga cada
#: mecanismo. Un simbolo que necesitara algo de fuera de este mapa no seria
#: BUILDABLE, y el suite lo exige (``test_no_symbol_declares_a_dependency_...``).
INVENTORY = {
    ('cpython', 'contención por bytecode'): '',
    ('cpython', 'evaluación y control de flujo'): '',
    ('django', 'evaluación y control de flujo'): '',
    ('django', 'almacén del arch por key'): '',
    ('django', 'formateo por locale'): '',
    ('django', 'recorrido del árbol a dict'): '',
    ('drf', 'contrato del endpoint'): '',
    ('lxml', 'parseo, XPath y construcción de nodos'): '',
    ('lxml', 'herencia entre vistas por XPath'): '',
    ('postgresql', 'guardar y consultar el arch'): '',
    ('gunicorn', 'servir el documento'): '',
    ('libharu', 'emitir el PDF'): '',
    ('libharu', 'leer y fusionar el PDF'): '',
    ('pypdf', 'leer y fusionar el PDF'): '',
}

READY = 'READY'
BUILDABLE = 'BUILDABLE'
BLOCKED = 'BLOCKED'


@dataclass(frozen=True)
class Symbol:
    """Un simbolo de la referencia y con que se paga aqui."""

    name: str
    reference: str
    installed: list
    primitives: list
    inventory: tuple


@dataclass(frozen=True)
class Verdict:
    """El cubo de un simbolo, y lo que falto si quedo bloqueado."""

    name: str
    bucket: str
    inventory: tuple
    missing: list = field(default_factory=list)


#: Los siete del tramo 5, en el orden de la referencia.
SYMBOLS = [
    Symbol(
        name='setup_signaling',
        reference='odoo19c: odoo/orm/registry.py:1036',
        installed=[],
        primitives=['django.db.connections', 'tools.sql.SQL',
                    'orm.registry._CACHES_BY_KEY'],
        inventory=('postgresql', 'guardar y consultar el arch'),
    ),
    Symbol(
        name='get_sequences',
        reference='odoo19c: odoo/orm/registry.py:1066',
        installed=[],
        primitives=['tools.sql.SQL', 'orm.registry._CACHES_BY_KEY'],
        inventory=('postgresql', 'guardar y consultar el arch'),
    ),
    Symbol(
        name='check_signaling',
        reference='odoo19c: odoo/orm/registry.py:1076',
        installed=[],
        primitives=['contextlib.closing', 'contextlib.nullcontext',
                    'orm.registry.Registry.new', 'orm.registry._CACHES_BY_KEY'],
        inventory=('cpython', 'evaluación y control de flujo'),
    ),
    Symbol(
        name='signal_changes',
        reference='odoo19c: odoo/orm/registry.py:1110',
        installed=[],
        primitives=['django.db.connections', 'tools.sql.SQL'],
        inventory=('postgresql', 'guardar y consultar el arch'),
    ),
    Symbol(
        name='reset_changes',
        reference='odoo19c: odoo/orm/registry.py:1142',
        installed=[],
        primitives=['contextlib.closing', 'orm.registry._CACHES_BY_KEY'],
        inventory=('cpython', 'evaluación y control de flujo'),
    ),
    Symbol(
        name='manage_changes',
        reference='odoo19c: odoo/orm/registry.py:1155',
        installed=[],
        primitives=['contextlib.contextmanager', 'warnings.warn'],
        inventory=('cpython', 'evaluación y control de flujo'),
    ),
    Symbol(
        name='cursor',
        reference='odoo19c: odoo/orm/registry.py:1165',
        #: Django ya entrega el cursor: ``connections[alias].cursor()`` hace lo
        #: que ``self._db.cursor()`` de la fuente, con su propio pool.
        installed=['django.db.connections'],
        primitives=['django.db.connections'],
        inventory=('django', 'evaluación y control de flujo'),
    ),
]


def resolve(dotted):
    """El objeto que nombra ``dotted``, o ``None`` si no existe.

    Prueba prefijos de mas largo a mas corto como modulo, y lo que queda como
    cadena de atributos. Asi ``orm.registry.Registry.new`` resuelve aunque
    ``orm.registry.Registry`` no sea un modulo.
    """
    parts = dotted.split('.')
    for cut in range(len(parts), 0, -1):
        try:
            found = importlib.import_module('.'.join(parts[:cut]))
        except ImportError:
            continue
        for attribute in parts[cut:]:
            found = getattr(found, attribute, None)
            if found is None:
                return None
        return found
    return None


def classify(symbol):
    """El cubo de un simbolo — READY, BUILDABLE o BLOCKED."""
    if symbol.installed and all(resolve(path) is not None
                                for path in symbol.installed):
        return Verdict(symbol.name, READY, symbol.inventory)
    missing = [path for path in symbol.primitives if resolve(path) is None]
    if missing:
        return Verdict(symbol.name, BLOCKED, symbol.inventory, missing)
    return Verdict(symbol.name, BUILDABLE, symbol.inventory)


def report():
    """``{cubo: [nombre, ...]}`` con los tres cubos siempre presentes."""
    buckets = {READY: [], BUILDABLE: [], BLOCKED: []}
    for symbol in SYMBOLS:
        buckets[classify(symbol).bucket].append(symbol.name)
    return buckets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--json', action='store_true',
                        help='emite el reparto como JSON')
    parser.add_argument('--strict', action='store_true',
                        help='sale 1 si algun simbolo queda BLOCKED')
    options = parser.parse_args(argv)

    verdicts = [classify(symbol) for symbol in SYMBOLS]
    buckets = report()
    if options.json:
        print(json.dumps({
            'buckets': buckets,
            'verdicts': [{'name': v.name, 'bucket': v.bucket,
                          'inventory': list(v.inventory), 'missing': v.missing}
                         for v in verdicts],
        }, ensure_ascii=False, indent=2))
    else:
        for verdict in verdicts:
            origin, topic = verdict.inventory
            line = f'{verdict.bucket:<9} {verdict.name:<18} {origin}/{topic}'
            if verdict.missing:
                line += '  falta: ' + ', '.join(verdict.missing)
            print(line)
        print(f'\nREADY {len(buckets[READY])} · BUILDABLE '
              f'{len(buckets[BUILDABLE])} · BLOCKED {len(buckets[BLOCKED])} '
              f'(alcance medido: {len(SYMBOLS)} simbolos del tramo)')
    return 1 if options.strict and buckets[BLOCKED] else 0


if __name__ == '__main__':
    sys.exit(main())
