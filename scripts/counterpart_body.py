#!/usr/bin/env python3
"""Motor: comparar una PROPIEDAD DEL CUERPO contra la contraparte de la fuente.

Los gates de este arbol miden la **presencia** de un simbolo
(``check_porte_completo``), su **cabecera** (``check_model_class_attributes``),
su **sitio** (``check_symbol_home``) o una convencion de nombre. Ninguno leia
el cuerpo para preguntarse **como** hace lo que hace, y por ese hueco entro
H-API-1058: un reflejo escribia por ``update_or_create`` —cruzando la guarda
de ``save()``— donde la fuente escribe por SQL crudo a proposito.

Este modulo es el mecanismo de esa comparacion. **No sabe que propiedad se
mide**: recibe un :class:`Axis` que declara los dos vocabularios y como se
nombra cada desacuerdo. El primer eje es el camino de escritura
(``check_write_path.py``); los siguientes —si transacciona, si emite senales,
por que via lee— se declaran igual, sin escribir otro recorrido.

**Por que un modulo aparte y no dentro de** ``check_porte_completo``. El
precedente del arbol es :ref:`h-api-955`, que partio un ``graph_algorithms.py``
en tres por SRP: *"los tres cambian por razones distintas"*. Aqui pasa lo
mismo — el recorrido cambia cuando cambia como se resuelve un espejo; el eje,
cuando cambia que se mide. Pesado por los siete factores: **claridad** y
**mantenimiento** ganan con la separacion, y el **coste** es una invocacion
mas en el pre-commit, que son milisegundos sobre archivos en staging.
"""
import ast
import dataclasses
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import reference_roots  # noqa: E402 — la raiz se declara una vez (H-API-335)

#: Las dos categorias transversales, que ningun eje redefine. ``ABSENT`` es lo
#: que el eje NO ve en ese cuerpo; ``BOTH`` es su propia categoria y no se
#: colapsa a ninguna de las dos del eje, porque dice algo distinto.
ABSENT = 'sin senal'
BOTH = 'ambas'

#: El instrumento vio los dos lados y **no puede decidir** con su granularidad.
#: No es un hallazgo —no hay defecto que nombrar— ni un acuerdo. Se cuenta
#: aparte para que el denominador no lo esconda: un par indeterminado contado
#: como acuerdo publica un verde que no discrimina (sub-patron D de
#: ``metrica-decide-la-conclusion.md``).
INDETERMINATE = 'indeterminado por granularidad de metodo'


@dataclasses.dataclass(frozen=True)
class Vocabulary:
    """Los nombres de llamada de un lado, en las dos categorias del eje."""

    side: str
    first: frozenset
    second: frozenset


@dataclasses.dataclass(frozen=True)
class Axis:
    """Que propiedad se mide, y como se nombra cada desacuerdo.

    ``first_name``/``second_name`` son las etiquetas legibles de las dos
    categorias. ``directions`` mapea ``(nuestra, la de la fuente)`` al nombre
    del riesgo: sin entrada, el desacuerdo se reporta sin nombrar direccion,
    que es honesto y no inventa una lectura.
    """

    name: str
    ours: Vocabulary
    reference: Vocabulary
    first_name: str
    second_name: str
    directions: dict


def called_names(node):
    """Los nombres invocados en el cuerpo, por atributo o sueltos."""
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Attribute):
            yield sub.func.attr
        elif isinstance(sub.func, ast.Name):
            yield sub.func.id


def classify(node, vocabulary, axis):
    """La categoria del cuerpo segun el vocabulario de su lado."""
    first = second = False
    for name in called_names(node):
        if name in vocabulary.first:
            first = True
        elif name in vocabulary.second:
            second = True
    if first and second:
        return BOTH
    if first:
        return axis.first_name
    if second:
        return axis.second_name
    return ABSENT


def direction(ours, theirs, axis):
    """El nombre del desacuerdo, ``None`` si coinciden, ``INDETERMINATE`` si el
    instrumento no puede decidir.

    Tres desenlaces, no dos, y el tercero es el que evita un falso positivo:

    - Un lado **sin senal** no se compara: concluir ahi seria hablar de lo que
      el instrumento no ve (``metrica-decide-la-conclusion.md``).
    - Un lado en ``BOTH`` que **contiene** la categoria del otro es
      **indeterminado**, no un desacuerdo. La unidad de esta comparacion es el
      **metodo**, y un metodo puede escribir por dos mecanismos para dos
      operaciones distintas —insertar por debajo, borrar por el enganche—.
      Con esa granularidad, que nosotros usemos uno de los dos que la fuente
      usa no es evidencia de divergencia: es la resolucion del instrumento.
    - Lo demas es desacuerdo, con el nombre que el eje le de.
    """
    if ABSENT in (ours, theirs) or ours == theirs:
        return None
    if BOTH in (ours, theirs):
        return INDETERMINATE
    return axis.directions.get((ours, theirs), 'categoria distinta')


@dataclasses.dataclass(frozen=True)
class Finding:
    path: str
    symbol: str
    ours: str
    theirs: str
    direction: str

    @property
    def key(self):
        return f'{self.path}::{self.symbol}'


@dataclasses.dataclass(frozen=True)
class Scope:
    """El denominador. Un conteo sin el no es un resultado."""

    files_scanned: int
    files_with_counterpart: int
    pairs_compared: int
    pairs_indeterminate: int = 0


#: Las raices espejadas: el prefijo nuestro y su destino en la referencia. Las
#: rutas salen de ``reference_roots``; aqui solo vive el mapa de prefijos.
MIRRORED_ROOTS = (
    (('src', 'orm'), ('odoo', 'orm')),
    (('src', 'tools'), ('odoo', 'tools')),
)


def counterpart(path):
    """El archivo espejo en la referencia, o ``None`` si no lo hay."""
    parts = pathlib.Path(path).parts
    for prefix, destination in MIRRORED_ROOTS:
        if parts[:len(prefix)] == prefix:
            return reference_roots.tree().joinpath(
                *destination, *parts[len(prefix):])
    if parts[:2] == ('src', 'addons') and len(parts) > 3:
        return reference_roots.addon_root(parts[2]).joinpath(*parts[3:])
    return None


def methods_of(path):
    """Los metodos declarados en clases del archivo, por nombre."""
    try:
        tree = ast.parse(pathlib.Path(path).read_text(errors='ignore'))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return {}
    return {member.name: member
            for klass in ast.walk(tree) if isinstance(klass, ast.ClassDef)
            for member in klass.body
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))}


def compare(paths, axis):
    """Los hallazgos del eje y el alcance sobre el que se midieron."""
    paths = list(paths)
    findings, with_counterpart, pairs, indeterminate = [], 0, 0, 0
    for path in paths:
        reference = counterpart(path)
        if reference is None or not reference.is_file():
            continue
        with_counterpart += 1
        ours, theirs = methods_of(path), methods_of(reference)
        for name, node in ours.items():
            if name not in theirs:
                continue
            mine = classify(node, axis.ours, axis)
            yours = classify(theirs[name], axis.reference, axis)
            if ABSENT in (mine, yours):
                continue
            pairs += 1
            verdict = direction(mine, yours, axis)
            if verdict == INDETERMINATE:
                indeterminate += 1
            elif verdict is not None:
                findings.append(Finding(str(path), name, mine, yours, verdict))
    return findings, Scope(len(paths), with_counterpart, pairs, indeterminate)


def tree_files(roots):
    """Los ``.py`` de las raices dadas, saltando cache y migraciones."""
    for root in roots:
        base = pathlib.Path(root)
        if base.is_file():
            yield base
            continue
        for path in sorted(base.rglob('*.py')):
            if '__pycache__' in path.parts or 'migrations' in path.parts:
                continue
            yield path


def load_baseline(path):
    """La deuda congelada. Una entrada listada no bloquea; una nueva si."""
    baseline = pathlib.Path(path)
    if not baseline.is_file():
        return set()
    return {line.strip() for line in baseline.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def write_baseline(path, findings, note):
    pathlib.Path(path).write_text(
        f'# {note}\n'
        '# Una entrada listada no bloquea; una nueva si. Se paga al tocar el\n'
        '# archivo, no en un barrido.\n'
        + ''.join(f'{f.key}\n' for f in sorted(findings, key=lambda x: x.key)))
    return len(findings)
