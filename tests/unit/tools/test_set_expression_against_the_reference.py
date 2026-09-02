"""``tools.set_expression`` medido contra la fuente, ejecutandola.

**Por que existe, si ya hay ``test_set_expression.py``.** Aquel porta los quince
casos de ``odoo19c: addons/base/tests/test_groups.py`` y mide lo que la fuente
decidio mirar. Este mide otra cosa: **ejecuta el modulo de la referencia** y
compara su conducta con la nuestra sobre una bateria generada, operacion por
operacion. No hay aserciones escritas a mano — el oraculo es la fuente misma.

Se puede hacer porque los dos modulos son **stdlib pura**: la fuente importa
``ast``, ``abc`` y ``typing``, y nada de Odoo. Es el unico archivo del arbol
donde el porte se puede contrastar asi.

La lectura de ``odoo-tools`` es de SOLO LECTURA: se carga el archivo por ruta
con ``importlib``, no se escribe nada.

**Que anade sobre el archivo a mano, medido y no supuesto.** Los tres
sabotajes que se probaron caen en los dos archivos, asi que el diferencial
**no** rescata un verde falso de aquel:

======================================  ==========  ============
sabotaje                                a mano      diferencial
======================================  ==========  ============
``isdisjoint.self.negative`` invertido   6 failed    1 failed
``UnknownId.__lt__`` siempre True        2 failed    1 failed
``_union_merge`` salta una rama          7 failed    1 failed
======================================  ==========  ============

Lo que aporta es **alcance**: aquel mide los quince casos que los autores de
la fuente decidieron mirar; este mide 978 expresiones contra cada operacion,
sin elegir. Y el a mano localiza mejor —falla en varios casos con nombre—,
asi que ninguno sustituye al otro.

*Metrica:* valor devuelto —o el nombre de la excepcion, que tambien es conducta
observable— de ``str``, ``repr``, ``key``, ``is_empty``, ``is_universal``,
``bool``, ``from_key``, ``parse``, ``matches`` sobre los 256 subconjuntos de
ids, y ``get_id`` / ``get_superset_ids`` / ``get_subset_ids`` /
``get_disjoint_ids``, para cada elemento de la bateria.
*Ciega a:* el rendimiento y el numero de pasos de la simplificacion; a las
definiciones que no esten en el fixture (ocho conjuntos con supraconjuntos y
disjuntos, no un universo arbitrario); y a cualquier divergencia que la fuente
comparta con nosotros, porque el oraculo es ella.
"""
import ast
import importlib.util
import itertools
import pathlib

import pytest

from tools import set_expression as ported

pytestmark = pytest.mark.unit

#: El declarador unico de rutas de la referencia — se carga por ruta porque
#: ``scripts/`` no es un paquete importable desde ``tests/``. Misma via que
#: ``tests/unit/orm/test_related_shape_in_the_reference.py``.
_REPO = pathlib.Path(__file__).resolve().parents[3]
_SPEC = importlib.util.spec_from_file_location(
    'reference_roots_for_set_expression', _REPO / 'scripts' / 'reference_roots.py')
reference_roots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reference_roots)

#: Los ocho conjuntos del fixture: dos jerarquias de supraconjuntos (A y B) y
#: un par disjunto (C, D). Son los ejes que la simplificacion usa para decidir.
DEFINITIONS = {
    1: {'ref': 'A'},
    2: {'ref': 'A1', 'supersets': [1]},
    3: {'ref': 'A11', 'supersets': [2]},
    4: {'ref': 'A2', 'supersets': [1]},
    5: {'ref': 'B'},
    6: {'ref': 'B1', 'supersets': [5]},
    7: {'ref': 'C'},
    8: {'ref': 'D', 'disjoints': [7]},
}
IDS = list(DEFINITIONS)


def reference_module():
    """Carga ``odoo/tools/set_expression.py`` de la referencia, o rinde None."""
    try:
        root = pathlib.Path(reference_roots.tree('odoo19c'))
    except Exception:                       # noqa: BLE001 — la raiz es opcional
        return None
    path = root / 'odoo' / 'tools' / 'set_expression.py'
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location('reference_set_expression', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def battery(definitions):
    """Hojas, sus negaciones, y los productos de cada PAR ORDENADO.

    El par tiene que ser ordenado y las negaciones tienen que entrar como
    semilla: el unico sitio que llama a ``Leaf.isdisjoint`` es
    ``Inter.__combine``, y su acumulador solo arranca con una hoja negativa si
    la interseccion se construyo con una delante. Con solo hojas positivas y
    ``combinations``, la rama ``self.negative`` de ``isdisjoint`` no se visita
    nunca — y una bateria que no la visita da verde con esa rama invertida.
    Lo mide ``test_the_battery_reaches_the_negative_branch``.
    """
    leaves = [definitions.from_ids([i]) for i in IDS]
    # Dos referencias que el fixture NO declara: ``parse`` las resuelve a una
    # hoja de ``UnknownId``, cuyo orden es una rama propia. Sin ellas la
    # bateria da verde con ``UnknownId.__lt__`` devolviendo siempre True — lo
    # mide ``test_the_battery_reaches_the_unknown_identifier``.
    leaves += [definitions.parse(ref, raise_if_not_found=False)
               for ref in ('unknown.one', 'unknown.two')]
    seeds = leaves + [~leaf for leaf in leaves]
    built = list(seeds) + [definitions.empty, definitions.universe]
    for left, right in itertools.permutations(seeds, 2):
        built += [left & right, left | right, ~(left & right),
                  (left | right) & ~left, left.invert_intersect(right)]
    # ``invert_intersect`` devuelve None cuando el resultado no esta definido;
    # dejarlos dentro compararia None contra None y engordaria el denominador
    # sin medir nada.
    return [expression for expression in built if expression is not None]


def observed(call):
    """El valor, o el NOMBRE de la excepcion: las dos son conducta observable."""
    try:
        return ('value', call())
    except Exception as error:              # noqa: BLE001 — la excepcion se compara
        return ('raises', type(error).__name__)


PROBES = (
    ('str', str),
    ('repr', repr),
    ('key', lambda expression: expression.key),
    ('is_empty', lambda expression: expression.is_empty()),
    ('is_universal', lambda expression: expression.is_universal()),
    ('bool', bool),
)


class TestTheBehaviourMatchesTheReference:
    """Ejecuta los dos modulos y compara su salida, no sus nombres."""

    def test_every_operation_returns_what_the_reference_returns(self):
        reference = reference_module()
        if reference is None:
            pytest.skip('la referencia no esta montada en esta sesion')

        their = reference.SetDefinitions(dict(DEFINITIONS))
        ours = ported.SetDefinitions(dict(DEFINITIONS))
        their_battery, our_battery = battery(their), battery(ours)
        divergences = []
        comparisons = 0

        def compare(label, theirs, mine):
            nonlocal comparisons
            comparisons += 1
            left, right = observed(theirs), observed(mine)
            if left != right:
                divergences.append((label, left, right))

        compare('battery size', lambda: len(their_battery), lambda: len(our_battery))
        for identifier in IDS:
            ref_name = DEFINITIONS[identifier]['ref']
            compare(f'get_id({ref_name})',
                    lambda n=ref_name: their.get_id(n), lambda n=ref_name: ours.get_id(n))
            for name in ('get_superset_ids', 'get_subset_ids', 'get_disjoint_ids'):
                compare(f'{name}({identifier})',
                        lambda n=name, i=identifier: sorted(getattr(their, n)([i])),
                        lambda n=name, i=identifier: sorted(getattr(ours, n)([i])))
        compare('get_id(absent)',
                lambda: their.get_id('NOT_A_REF'), lambda: ours.get_id('NOT_A_REF'))

        for index, (theirs, mine) in enumerate(zip(their_battery, our_battery)):
            for name, probe in PROBES:
                compare(f'[{index}] {name}',
                        lambda p=probe, x=theirs: p(x), lambda p=probe, x=mine: p(x))
            compare(f'[{index}] from_key',
                    lambda x=theirs: str(their.from_key(x.key)),
                    lambda x=mine: str(ours.from_key(x.key)))
            compare(f'[{index}] parse',
                    lambda x=theirs: str(their.parse(str(x))),
                    lambda x=mine: str(ours.parse(str(x))))
            for size in range(len(IDS) + 1):
                for subset in itertools.combinations(IDS, size):
                    compare(f'[{index}] matches{subset}',
                            lambda x=theirs, s=subset: x.matches(s),
                            lambda x=mine, s=subset: x.matches(s))

        assert comparisons > 100_000, (
            f'la bateria encogio a {comparisons} comparaciones: mide menos que '
            'cuando se escribio y su verde ya no dice lo mismo')
        assert not divergences, (
            f'{len(divergences)} de {comparisons} comparaciones divergen de la '
            f'fuente; las tres primeras: {divergences[:3]}')


class TestTheBatteryCoversWhatMakesItDiscriminate:
    """El control sobre el control — sin esto, el verde de arriba es un adorno.

    Una version anterior de la bateria emparejaba solo hojas positivas con
    ``combinations``. Daba **0 divergencias sobre 116 640 comparaciones** con la
    rama ``self.negative`` de ``Leaf.isdisjoint`` invertida a mano: verde con el
    codigo roto. La bateria de hoy la visita, y con la misma inversion da
    **25 312 divergencias sobre 258 225**.

    Este caso fija esa cobertura. Si alguien encoge la bateria, falla aqui —
    donde se ve la causa— y no en un porte futuro que pase por casualidad.
    """

    def test_the_battery_reaches_the_negative_branch(self):
        definitions = ported.SetDefinitions(dict(DEFINITIONS))
        reached = {'self.negative': 0, 'other.negative': 0, 'both positive': 0}
        original = ported.Leaf.isdisjoint

        def counting(self, other):
            if self.negative:
                reached['self.negative'] += 1
            elif other.negative:
                reached['other.negative'] += 1
            else:
                reached['both positive'] += 1
            return original(self, other)

        ported.Leaf.isdisjoint = counting
        try:
            battery(definitions)
        finally:
            ported.Leaf.isdisjoint = original

        assert reached['self.negative'] > 0, (
            'la bateria no visita la rama self.negative de Leaf.isdisjoint: '
            'invertirla no haria fallar la comparacion con la fuente')
        assert reached['other.negative'] > 0
        assert reached['both positive'] > 0

    def test_the_battery_reaches_the_unknown_identifier(self):
        """La bateria construye hojas de ``UnknownId``, no solo de id declarado.

        Medido: sin las dos referencias no declaradas, invertir
        ``UnknownId.__lt__`` daba **0 failed** en el diferencial y **2 failed**
        en los casos escritos a mano. El instrumento generado era ciego
        justo donde el escrito a mano veia.
        """
        definitions = ported.SetDefinitions(dict(DEFINITIONS))
        # Se lee por la CLAVE y no recorriendo la estructura: ``key`` es la
        # unica vista publica de las hojas, y es la CADENA que ``from_key``
        # vuelve a leer con ``ast.literal_eval`` — no una tupla. Recorrer
        # ``.leaves`` ataria el caso a la forma interna, que ``Union`` ni
        # siquiera expone con ese nombre.
        #
        # Un id declarado viaja como ``int``; el de una hoja no declarada es
        # un ``UnknownId``, subclase de ``str``, y ``literal_eval`` lo
        # devuelve como ``str``. El discriminador es el tipo, no la clase.
        tipos = {type(leaf_id).__name__
                 for expression in battery(definitions)
                 for inter in ast.literal_eval(expression.key)
                 for leaf_id, _negative in inter}
        assert 'str' in tipos, (
            f'la bateria solo construye ids de tipo {sorted(tipos)}: sin una '
            'hoja de UnknownId, una divergencia en su orden no la haria fallar')
        assert 'int' in tipos
