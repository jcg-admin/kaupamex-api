#!/usr/bin/env python3
"""Gate — un atributo de clase de campo responde lo que la fuente declara.

El defecto que atrapa
=====================

``orm.fields`` instala 45 atributos sobre ``models.Field`` con el defecto que
la fuente declara en su clase base. La fuente además los **sobrescribe** en
clases concretas: ``Integer.falsy_value = 0``, ``Id.readonly = True``,
``Monetary.write_sequence = 10``. Si esas sobrescrituras no se instalan, el
atributo **existe**, responde, y responde mal.

Es el verde que no discrimina (sub-patrón D de
``metrica-decide-la-conclusion.md``) aplicado a un atributo en vez de a un
test: ningún gate de porte lo ve ausente, porque no está ausente. Y no es
teórico — ``falsy_value`` cayó así, y lo destapó un consumidor al portarse, no
una auditoría (:ref:`h-api-970`).

Cómo mide
=========

Dos insumos, ninguno de memoria:

1. **Por AST sobre la fuente** — qué declara ``Field`` y qué sobrescribe cada
   clase concreta, leyendo ``$ODOO19C/odoo/orm/fields*.py``.
2. **En vivo** — ``getattr`` sobre la clase de Django que le corresponde, con
   el mapa ``orm.fields.REFERENCE_CLASS_TO_DJANGO``, que es donde vive el
   conocimiento de porte. El gate **no tiene su propia copia**: una segunda
   sería la segunda fuente de verdad que ``calibration-verified-numbers.md``
   prohíbe.

Incumplidor = la fuente declara una sobrescritura para esa clase y aquí la
clase de Django responde otra cosa.

Alcance
=======

Sólo los atributos que **ya instalamos**. Uno que la fuente declara y aquí no
existe es *ausencia*, no mentira: lo mide el censo de la tarea #227, y
mezclarlos aquí publicaría un conteo que junta dos fenómenos distintos.

Uso
===

    uv run python scripts/check_field_class_attributes.py            # reporte
    uv run python scripts/check_field_class_attributes.py --strict   # exit 1 si hay nuevos
    uv run python scripts/check_field_class_attributes.py --write-baseline

Corre con el intérprete del proyecto, no con ``python3``: mide **en vivo** con
``getattr`` sobre las clases de Django, así que necesita el entorno.
"""
import argparse
import ast
import os
import pathlib
import subprocess
import sys

BASELINE = pathlib.Path(__file__).parent / 'field_class_attributes_baseline.txt'
REFERENCE_FILES = 'fields*.py'
BASE_CLASS = 'Field'


def reference_root():
    """La raíz de la referencia, por el declarador único de rutas.

    Sin ella el gate **rehúsa con exit 2 y no emite conteo**: un 0 aquí no
    distinguiría «ninguna mentira» de «no pude leer la fuente», que es
    exactamente el verde falso que este gate existe para atrapar (H-API-335).
    """
    script = pathlib.Path(__file__).parent / 'reference_roots.py'
    if not script.is_file():
        sys.exit('ERROR — falta scripts/reference_roots.py; NO se emite conteo')
    salida = subprocess.run([sys.executable, str(script), '--env'],
                            capture_output=True, text=True)
    for line in salida.stdout.splitlines():
        if line.startswith('export ODOO19C='):
            root = pathlib.Path(line.split('=', 1)[1].strip().strip('"'))
            if (root / 'odoo' / 'orm').is_dir():
                return root
    sys.exit('ERROR — la referencia no esta montada; NO se emite conteo:\n'
             '  un 0 sin poder leer la fuente seria un verde falso.')


def declared_in_reference(root):
    """``({atributo: valor_de_Field}, {atributo: {clase: valor}}, {atributo})``.

    El tercer elemento son los atributos que la fuente declara en alguna clase
    como ``property`` o ``cached_property``. **No se pueden comparar por AST**:
    su valor depende de la instancia, no de la clase.

    Era la tercera ceguera del gate y la destapo el porte de #245. Sin este
    conjunto, corregir ``FloatField._column_type`` a ``('float8','float8')``
    —que es lo que la property de ``Float`` devuelve en su rama sin digitos—
    convertia el arreglo en un incumplidor nuevo: el AST no ve la property, asi
    que comparaba contra el defecto ``None`` de ``Field``. Un gate que marca
    como defecto el valor correcto es peor que no tenerlo.
    """
    base, overrides, computed, parents = {}, {}, set(), {}
    for path in sorted((root / 'odoo' / 'orm').glob(REFERENCE_FILES)):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.ClassDef):
                continue
            # La jerarquia DE LA FUENTE, para saber de quien hereda cada clase
            # cuando no declara el atributo. Sin esto el gate compara contra el
            # defecto de ``Field`` y publica como defecto lo que la clase
            # hereda bien de su padre: ``Html`` no declara ``falsy_value``, y
            # ``BaseString`` —su padre— dice ``''``, no ``None``.
            parents[node.name] = [
                b.id for b in node.bases if isinstance(b, ast.Name)
            ]
            for statement in node.body:
                name = None
                if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                        and isinstance(statement.targets[0], ast.Name)):
                    name = statement.targets[0].id
                elif (isinstance(statement, ast.AnnAssign)
                      and isinstance(statement.target, ast.Name)):
                    name = statement.target.id
                if not name or name.startswith('__') or statement.value is None:
                    continue
                literal = ast.unparse(statement.value)
                if node.name == BASE_CLASS:
                    base[name] = literal
                else:
                    overrides.setdefault(name, {})[node.name] = literal
            for statement in node.body:
                if not isinstance(statement, (ast.FunctionDef,
                                              ast.AsyncFunctionDef)):
                    continue
                decorators = {ast.unparse(d) for d in statement.decorator_list}
                if decorators & {'property', 'cached_property',
                                 'functools.cached_property'}:
                    computed.add(statement.name)

    return base, overrides, computed, parents


def inherited_literal(reference_name, attribute, overrides, parents, base):
    """``(clase_que_lo_declara, literal)`` siguiendo la jerarquia DE LA FUENTE.

    Sube por los ``bases`` que el AST leyo hasta dar con la primera clase que
    declara ``attribute``; si ninguna lo hace, cae al defecto de ``Field``.
    Sin este recorrido el gate compara toda clase que no declare el atributo
    contra ``Field``, y marca como incumplidora a la que lo hereda bien de un
    padre intermedio.
    """
    visited, pending = set(), [reference_name]
    while pending:
        current = pending.pop(0)
        if current in visited:
            continue
        visited.add(current)
        declared = overrides.get(attribute, {}).get(current)
        if declared is not None and current != reference_name:
            return (current, declared)
        pending.extend(parents.get(current, ()))
    return (BASE_CLASS, base[attribute])


def answered_here(django_class, attribute):
    """Lo que la clase de Django responde, o el centinela de ausencia."""
    return getattr(django_class, attribute, _MISSING)


class _Missing:
    def __repr__(self):
        return '<ausente>'


_MISSING = _Missing()


def agrees(answered, literal):
    """Si la respuesta viva casa con el literal que la fuente declara.

    El literal viene de ``ast.unparse``, así que se re-evalúa con
    ``ast.literal_eval`` cuando se puede y se compara por valor. Lo que **no**
    se hace es comparar por veracidad: la primera versión de esta función tenía

        if expected.startswith(('0', 'False', "''")) and not answered:
            return True

    y con eso ``None`` pasaba por ``0``. Es exactamente la distinción que
    ``falsy_value`` codifica —``None`` es *"este campo no tiene valor falsy"* y
    ``0`` es *"el cero cuenta como no establecido"*— así que el gate colapsaba
    el defecto que existe para atrapar. Lo destapó su propio control positivo:
    retirar ``Integer`` de la tabla no producía ningún incumplidor.

    Por eso las dos guardas explícitas: ``None`` nunca casa con un cero
    concreto, y un ``bool`` nunca casa con un entero aunque Python diga que
    ``True == 1``.
    """
    if answered is _MISSING:
        return False
    try:
        expected = ast.literal_eval(literal)
    except (ValueError, SyntaxError, TypeError):
        # Un literal que no es constante — ``('varchar', pg_varchar())``,
        # ``attrgetter(...)``— se compara por su forma escrita.
        return (repr(answered).replace(' ', '').replace('"', "'")
                == literal.replace(' ', '').replace('"', "'"))
    if (answered is None) != (expected is None):
        return False
    if isinstance(answered, bool) != isinstance(expected, bool):
        return False
    try:
        return answered == expected
    except TypeError:
        return False


def answered_here_by_name(django_name, attribute):
    """La respuesta viva, buscada por nombre de clase — sólo para el informe."""
    from django.db import models as django_models
    import orm.fields as our_fields
    for module in (django_models, our_fields):
        candidate = getattr(module, django_name, None)
        if isinstance(candidate, type):
            return answered_here(candidate, attribute)
    return _MISSING


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si hay incumplidores fuera del baseline')
    parser.add_argument('--write-baseline', action='store_true',
                        help='congela los incumplidores actuales')
    args = parser.parse_args()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'src'))
    try:
        import django
    except ModuleNotFoundError:
        # Este gate mide en VIVO, asi que necesita el interprete del proyecto.
        # Rehusa sin conteo: un 0 aqui no distinguiria «no hay mentiras» de
        # «no pude arrancar Django», que es el verde falso que existe para
        # atrapar.
        sys.exit('ERROR — este gate corre con el interprete del proyecto:\n'
                 '  uv run python scripts/check_field_class_attributes.py\n'
                 'NO se emite conteo.')
    django.setup()
    from orm.fields import (  # noqa: E402
        _FIELD_CLASS_ATTRIBUTES,
        REFERENCE_CLASS_TO_DJANGO,
    )

    from django.db import models  # noqa: E402

    root = reference_root()
    base, overrides, computed, parents = declared_in_reference(root)
    installed = set(_FIELD_CLASS_ATTRIBUTES)

    # EXCLUSION ESTRUCTURAL, declarada una vez y no cuarenta y cinco.
    #
    # El parche instala sobre ``models.Field``, asi que una clase fuera de esa
    # jerarquia no puede recibirlo — no es que responda mal, es que el
    # mecanismo no la alcanza. Marcarla en cada atributo publicaria 45 filas
    # que describen un solo hecho.
    unreachable = {
        name: [c.__name__ for c in classes if not issubclass(c, models.Field)]
        for name, classes in REFERENCE_CLASS_TO_DJANGO.items()
    }
    unreachable = {k: v for k, v in unreachable.items() if v}
    reachable = {
        name: tuple(c for c in classes if issubclass(c, models.Field))
        for name, classes in REFERENCE_CLASS_TO_DJANGO.items()
    }

    # SEGUNDA EXCLUSION, tambien declarada una vez: el atributo que la fuente
    # resuelve con una ``property`` en alguna clase. Su valor depende de la
    # instancia, asi que ningun recorrido por AST puede decir cual es el
    # correcto — y compararlo contra el defecto de ``Field`` publica como
    # defecto justo el valor que la property devuelve.
    computed_and_installed = sorted(computed & installed)

    offenders, measured, collisions = [], 0, []
    for attribute in sorted(installed & set(overrides)):
        if attribute not in base or attribute in computed:
            continue
        # Dos clases de la fuente que apuntan a la MISMA clase de Django y
        # declaran valores distintos: el atributo no puede satisfacer a las
        # dos. Es la ceguera declarada en h-api-970 (Selection y Char comparten
        # CharField). Se REPORTA en vez de elegir una en silencio.
        by_django = {}
        for reference_name, literal in overrides[attribute].items():
            for django_class in reachable.get(reference_name, ()):
                previous = by_django.get(django_class)
                if previous is not None and previous[1] != literal:
                    collisions.append(
                        f'{attribute}  {django_class.__name__}  '
                        f'{previous[0]}={previous[1]} vs {reference_name}={literal}')
                by_django[django_class] = (reference_name, literal)

        for django_class, (reference_name, literal) in by_django.items():
            measured += 1
            answer = answered_here(django_class, attribute)
            if not agrees(answer, literal):
                offenders.append(
                    f'{attribute}::{django_class.__name__}::{reference_name}')

        # SEGUNDA FORMA — la clase de la fuente **hereda** el defecto de
        # ``Field`` y aquí su contraparte hereda la sobrescritura de una
        # hermana. Es la divergencia de :ref:`h-api-970`: la fuente declara
        # ``class Id(Field)`` y Django declara ``AutoField(IntegerField)``, así
        # que la clave primaria responde el ``0`` que la fuente reserva para
        # ``Integer``.
        #
        # El gate nació ciego a esto —sólo miraba sobrescrituras— y lo destapó
        # su propio control positivo: retirar ``Id`` de la tabla de
        # ``falsy_value`` no producía ningún incumplidor. Un gate que sólo ve
        # la mitad de las formas publica un conteo que se lee como completo.
        for reference_name, django_classes in reachable.items():
            if reference_name in overrides[attribute]:
                continue                       # la cubre el bucle de arriba
            # Lo que hereda NO es siempre el defecto de ``Field``: puede
            # heredarlo de un padre intermedio que si lo declara. ``Html`` no
            # declara ``falsy_value`` y su padre ``BaseString`` dice ``''``,
            # no el ``None`` de ``Field``. Comparar contra ``Field`` publicaba
            # como defecto lo que la clase hereda BIEN — cuarta ceguera del
            # gate, destapada al entrar ``Html`` en el mapa de trasplante.
            expected = inherited_literal(reference_name, attribute,
                                         overrides, parents, base)
            for django_class in django_classes:
                if django_class in by_django:
                    continue                   # otra clase de la fuente manda
                measured += 1
                answer = answered_here(django_class, attribute)
                if not agrees(answer, expected[1]):
                    offenders.append(
                        f'{attribute}::{django_class.__name__}::'
                        f'{reference_name}(hereda {expected[0]})')

    key = lambda row: row  # noqa: E731
    frozen = set()
    if BASELINE.is_file():
        frozen = {line.strip() for line in BASELINE.read_text().splitlines()
                  if line.strip() and not line.startswith('#')}

    if args.write_baseline:
        BASELINE.write_text(
            '# Atributos de clase de campo que responden distinto de lo que la\n'
            '# fuente declara. Deuda heredada CONGELADA (tarea #245): uno\n'
            '# listado no bloquea, uno nuevo si. Se retira la linea al\n'
            '# corregirlo, o el baseline miente sobre deuda que ya no existe.\n'
            + '\n'.join(sorted(offenders, key=key)) + '\n')
        print(f'baseline escrito: {len(offenders)} entradas')
        return 0

    fresh = sorted(set(offenders) - frozen, key=key)

    for row in collisions:
        print(f'COLISION — dos clases de la fuente sobre la misma de Django:\n  {row}')
    if collisions:
        print()

    if fresh:
        print(f'FAIL — {len(fresh)} atributo(s) responden distinto de la fuente,\n'
              f'       fuera del baseline:\n')
        for row in fresh:
            attribute, django_name, reference_name = row.split('::')
            if '(hereda ' in reference_name:
                # La fila de la segunda forma trae de quien hereda, que ya no
                # es siempre ``Field``: puede ser un padre intermedio.
                declarer = reference_name.split('(hereda ')[1].rstrip(')')
                literal = (base[attribute] if declarer == BASE_CLASS
                           else overrides[attribute][declarer])
                origen = f'{reference_name.split("(")[0]} hereda {declarer}='
            else:
                literal = overrides[attribute][reference_name]
                origen = f'{reference_name}='
            print(f'  {attribute:18s} {django_name:16s} '
                  f'la fuente declara {origen}{literal}  '
                  f'(aqui: {answered_here_by_name(django_name, attribute)!r})')
        print('\nEl mecanismo esta construido: install_class_attribute_overrides() en\n'
              'src/orm/fields.py instala por clase concreta. Se extiende, no se\n'
              'inventa uno nuevo.')
    else:
        print('OK: cada atributo responde lo que la fuente declara')

    print(f'\n(alcance medido: {measured} pares atributo-clase sobre '
          f'{len(installed)} atributos instalados; '
          f'{len(offenders)} incumplidor(es), {len(frozen)} en baseline)')
    if unreachable:
        detalle = '; '.join(f'{k} -> {", ".join(v)}' for k, v in unreachable.items())
        print(f'(fuera del alcance por construccion: {detalle} — no desciende de '
              f'models.Field, asi que el parche de clase no la alcanza)')
    if computed_and_installed:
        print(f'(fuera del alcance por forma: {", ".join(computed_and_installed)} '
              f'— la fuente los resuelve con una property en alguna clase, y su '
              f'valor depende de la instancia; ningun recorrido por AST puede '
              f'decidirlos. Su control es de conducta: '
              f'tests/unit/orm/test_field_class_attributes.py)')
    return 1 if (fresh and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
