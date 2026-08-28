#!/usr/bin/env python3
"""Gate de la convención de nombre de columna en las FK portadas (ADR-029, #141).

La referencia colapsa en un nombre lo que Django separa en tres ejes, así que
una FK portada admite cuatro formas y sólo una es fiel a los dos que importan:

======  =========================================  =========  ==========
Forma   Declaración                                Símbolo    Columna
======  =========================================  =========  ==========
A       ``parent = Many2one(...)``                 divergente fiel
B       ``crud_model_id = Many2one(...)``          fiel       ``..._id_id``
C       ``model_id = Many2one(..., db_column=…)``  fiel       fiel
D       ``page = Many2one(..., db_column='…_id')`` divergente fiel
N       ``Many2one(store=False)``                  fiel       (sin columna)
======  =========================================  =========  ==========

ADR-029 fija **C** como la forma que gobierna. Este gate mide la forma de cada
declaración; NO lleva el conteo del árbol —eso lo publica al correr, y el
registro fechado vive en ``docs: source/gestion/pm/reportes/censo-convencion-fk-sufijo-id.rst``
(``calibration-verified-numbers.md``, corolario de la cifra que vive en código).

Qué NO puede ver
================

Un ``db_column`` construido en tiempo de ejecución, un campo declarado por
``contribute_to_class`` fuera de un ``ClassDef``, y el caso en que el símbolo
divergente sea el correcto porque el modelo es propio del L0 y no adapta nada
de la referencia. Ése es el motivo de que la forma A vaya a baseline en vez de
bloquear: la forma sola no distingue un porte con símbolo divergente de un
modelo nuestro que nunca tuvo contraparte.
"""
import argparse
import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BASELINE = REPO / 'scripts' / 'fk_naming_baseline.txt'

#: Los constructores de UN solo valor relacional. ``fields.Many2one`` es
#: nuestro despachador (``src/orm/fields_relational.py``): con ``store=True``
#: devuelve un ``models.ForeignKey``, así que las dos formas de declararlo
#: producen los mismos tres ejes y las dos se miden.
SINGLE_VALUED = ('Many2one', 'ForeignKey', 'OneToOneField')

#: Raíces del monolito modular. ``addons`` son los de comunidad portados;
#: ``src`` es el núcleo espejado.
ROOTS = ('src', 'addons')


def classify(field_name, has_db_column, stored=True):
    """La letra de la forma en que se declaró este campo.

    ``stored=False`` sale antes que las otras cuatro y no es una quinta forma:
    es la **ausencia del eje**. Un ``Many2one(store=False)`` devuelve un
    ``NonStored`` (``src/orm/fields_nonstored.py``), que no tiene columna, así
    que preguntar si la suya es fiel no significa nada. Meterlo en el cubo B
    —«columna divergente»— rotularía como defecto un campo que no tiene el eje
    donde se mide: el sub-patrón A de ``metrica-decide-la-conclusion.md``.
    """
    if not stored:
        return 'N'
    faithful_symbol = field_name.endswith('_id')
    if faithful_symbol:
        return 'C' if has_db_column else 'B'
    return 'D' if has_db_column else 'A'


def _keyword(call, name):
    """El valor de la palabra clave ``name`` de la llamada, o ``None``."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def declarations(path):
    """Cada asignación relacional de un solo valor: ``(clase, campo, forma)``."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError):
        return
    for klass in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for node in klass.body:
            # La referencia 19 declara el campo CON anotación de tipo —
            # ``parent_id: ResPartner = fields.Many2one(...)`` es un
            # ``ast.AnnAssign``. Un recorrido que sólo mire ``ast.Assign`` deja
            # de ver la declaración en cuanto el porte adopta esa forma, y
            # publica un 0 que no distingue «no hay deuda» de «no puedo verla»
            # (sub-patrón D de ``metrica-decide-la-conclusion.md``).
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            ctor = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if ctor not in SINGLE_VALUED:
                continue
            store = _keyword(node.value, 'store')
            stored = not (isinstance(store, ast.Constant) and store.value is False)
            has_column = _keyword(node.value, 'db_column') is not None
            for target in targets:
                if isinstance(target, ast.Name):
                    yield klass.name, target.id, classify(target.id, has_column, stored)


def python_files():
    """Los ``.py`` del monolito, sin migraciones ni cachés."""
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob('*.py')):
            parts = path.parts
            if 'migrations' in parts or '__pycache__' in parts:
                continue
            yield path


def load_baseline():
    if not BASELINE.is_file():
        return set()
    return {line.strip() for line in BASELINE.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def survey():
    """``(forma, clave)`` de cada declaración medida, con su conteo por forma."""
    rows, counts = [], {letter: 0 for letter in 'ABCDN'}
    for path in python_files():
        relative = path.relative_to(REPO)
        for klass, field, form in declarations(path):
            counts[form] += 1
            rows.append((form, f'{relative}::{klass}.{field}'))
    return rows, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si aparece una declaración no fiel nueva')
    parser.add_argument('--write-baseline', action='store_true',
                        help='congela la deuda heredada (formas A, B y D)')
    args = parser.parse_args()

    rows, counts = survey()
    measured = sum(counts.values())
    offenders = sorted(key for form, key in rows if form in ('A', 'B', 'D'))

    if args.write_baseline:
        BASELINE.write_text(
            '# Deuda heredada de ADR-029 — formas A/B/D congeladas.\n'
            '# Una listada no bloquea; una nueva sí. Se paga al tocar el\n'
            '# archivo (barrido: tarea #143).\n'
            + '\n'.join(offenders) + '\n')
        print(f'baseline escrito: {len(offenders)} declaraciones')
        return 0

    baseline = load_baseline()
    fresh = [key for key in offenders if key not in baseline]

    print(f'formas: ' + ' · '.join(f'{k}={v}' for k, v in sorted(counts.items()))
          + f'  (alcance medido: {measured} declaraciones relacionales '
            f'de un solo valor en {"/".join(ROOTS)})')
    print(f'no fieles: {len(offenders)}  ·  en baseline: {len(offenders) - len(fresh)}'
          f'  ·  nuevas: {len(fresh)}')
    for key in fresh:
        print(f'  NUEVA  {key}')

    if fresh and args.strict:
        print('\nADR-029: la columna lleva el nombre que la referencia declara.\n'
              "Forma C: símbolo fiel + db_column='<mismo nombre>'.", file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
