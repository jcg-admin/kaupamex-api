"""``tools.set_expression`` — el álgebra de conjuntos con nombre.

Adaptación de ``odoo19c: odoo/addons/base/tests/test_groups.py`` (LGPL-3),
clase ``TestGroupsObject`` (``:8-478``) — los quince casos que ejercitan el
álgebra pura, sin base de datos. La segunda clase de ese archivo
(``TestGroupsOdoo``) ejercita ``res.groups`` contra la base y no entra aquí:
su hogar es ``tests/integration/base/``.

Las definiciones del fixture y **cada aserción son verbatim de la fuente**: son
el contrato del mecanismo, no una elección de este puerto. Un cambio de
semántica en la simplificación —que es lo que hace útil al álgebra— falla aquí
aunque el símbolo siga existiendo.

Tres casos no salen de ``TestGroupsObject`` sino del **docstring del propio
módulo portado**, que declara los supraconjuntos, subconjuntos y disjuntos de
"Q" en el ejemplo de los números: ``get_superset_ids``, ``get_subset_ids`` y
``get_disjoint_ids`` no tienen caso en la fuente, y sin ellos tres símbolos
públicos quedarían portados sin control.

*Métrica:* los símbolos públicos de ``SetDefinitions`` y ``SetExpression``, con
al menos un caso por operación del álgebra (``&``, ``|``, ``~``, ``<=``, ``<``,
``==``, ``matches``, ``invert_intersect``, ``key``).
*Ciega a:* el rendimiento de la simplificación — ``test_a_huge_combination``
comprueba el resultado, no el número de pasos que costó llegar a él.
"""
import pytest

from tools.set_expression import SetDefinitions

pytestmark = pytest.mark.unit


@pytest.fixture(scope='module')
def definitions():
    """Los dieciséis conjuntos del fixture de la fuente (``:12-31``)."""
    return SetDefinitions({
        1: {'ref': 'A'},
        2: {'ref': 'A1', 'supersets': [1]},         # A1 <= A
        3: {'ref': 'A11', 'supersets': [2]},        # A11 <= A1
        4: {'ref': 'A2', 'supersets': [1]},         # A2 <= A
        5: {'ref': 'A21', 'supersets': [4]},        # A21 <= A2
        6: {'ref': 'A22', 'supersets': [4]},        # A22 <= A2
        7: {'ref': 'B'},
        8: {'ref': 'B1', 'supersets': [7]},         # B1 <= B
        9: {'ref': 'B11', 'supersets': [8]},        # B11 <= B1
        10: {'ref': 'B2', 'supersets': [7]},        # B2 <= B
        11: {'ref': 'BX',
             'supersets': [7],                      # BX <= B
             'disjoints': [8, 10]},                 # BX disjunto de B1, B2
        12: {'ref': 'A1B1', 'supersets': [2, 8]},   # A1B1 <= A1, B1
        13: {'ref': 'C'},
        14: {'ref': 'D', 'disjoints': [1, 7]},      # D disjunto de A, B
        15: {'ref': 'E', 'disjoints': [1, 7, 14]},  # E disjunto de A, B, D
        16: {'ref': 'E1', 'supersets': [15]},       # E1 <= E (y por tanto disjunto de A, B, D)
    })


def test_a_parsed_set_is_hashable_and_prints_its_reference(definitions):
    a = definitions.parse('A')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')

    assert hash(a), 'el objeto de grupo tiene que ser hashable'
    assert str(a) == "'A'"
    assert str(b) == "'B'"
    assert str(b1) == "'B1'"


def test_the_intersection_reduces_by_inclusion_and_by_disjunction(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b11 = definitions.parse('B11')
    bx = definitions.parse('BX')
    universe = definitions.universe
    empty = definitions.empty

    assert str(a & b) == "'A' & 'B'"
    assert str(b & a) == "'A' & 'B'"
    assert str(b & bx) == "'BX'"
    assert str(b1 & bx) == "~*"
    assert str(b11 & bx) == "~*"
    assert str(empty & empty) == "~*"
    assert str(a & universe) == "'A'"
    assert str(a & empty) == "~*"
    assert str(a1 & ~a) == "~*"
    assert str(a & a1 & universe) == "'A1'"


def test_the_union_absorbs_the_subset(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b11 = definitions.parse('B11')
    b2 = definitions.parse('B2')
    bx = definitions.parse('BX')
    universe = definitions.universe
    empty = definitions.empty

    assert str(a | a) == "'A'"
    assert str(a | b) == "'A' | 'B'"
    assert str(a1 | a) == "'A'"
    assert str(a | a1) == "'A'"
    assert str(a | b1) == "'A' | 'B1'"
    assert str(b | a) == "'A' | 'B'"
    assert str(b | bx) == "'B'"
    assert str(b1 | bx) == "'B1' | 'BX'"
    assert str(b11 | bx) == "'B11' | 'BX'"
    assert str(empty | empty) == "~*"
    assert str(a | b11 | b2) == "'A' | 'B11' | 'B2'"
    assert str(a | b2 | b11) == "'A' | 'B11' | 'B2'"
    assert str(a | empty) == "'A'"
    assert str(a | universe) == "*"
    assert str((a | a1) | empty) == "'A'"


def test_the_union_distributes_over_the_intersection(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a2 = definitions.parse('A2')
    b1 = definitions.parse('B1')
    b2 = definitions.parse('B2')
    universe = definitions.universe
    empty = definitions.empty

    assert str((a & b1) | b2) == "('A' & 'B1') | 'B2'"
    assert str(a | b1 & b2) == "'A' | ('B1' & 'B2')"
    assert str(a | a1 & universe) == "'A'"
    assert str((a1 | a2) & (b1 | b2)) == "('A1' & 'B1') | ('A1' & 'B2') | ('A2' & 'B1') | ('A2' & 'B2')"
    assert str(a | (a1 | empty)) == "'A'"
    assert str((a & a1) | empty) == "'A1'"
    assert str(a & (a1 | empty)) == "'A1'"


def test_the_comparison_follows_the_declared_inclusion(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a11 = definitions.parse('A11')
    a2 = definitions.parse('A2')
    a21 = definitions.parse('A21')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b11 = definitions.parse('B11')
    b2 = definitions.parse('B2')
    a1b1 = definitions.parse('A1B1')

    assert (a == a) is True
    assert (a == b) is False

    assert (a >= a1) is True
    assert (a >= a) is True
    assert ((a & b) >= b) is False
    assert (b1 >= a1b1) is True
    assert (b1 >= (a1 | a1b1)) is False
    assert (b >= (a & b)) is True

    assert (a > b) is False
    assert (a > a1) is True
    assert (a1 > a) is False
    assert (a > a) is False
    assert (a > a11) is True
    assert (a > a2) is True
    assert (a > a21) is True
    assert (a1 > a11) is True
    assert (a2 > a11) is False
    assert (a2 > a21) is True
    assert (a > b1) is False
    assert (a > b11) is False
    assert (a > b2) is False

    assert (a <= a) is True
    assert (a1 <= a) is True
    assert ((a & b) <= b) is True
    assert ((a & b) <= a) is True
    assert (b1 <= (a1 | a1b1)) is False
    assert (b <= (a & b)) is False
    assert (a <= (a & b)) is False
    assert (a <= (a | b)) is True

    assert (a < b) is False
    assert (a < a1) is False
    assert (a1 < a) is True
    assert (a < a11) is False
    assert (a < a2) is False
    assert (a < a21) is False
    assert (a < b1) is False
    assert (a < b11) is False
    assert (a < b2) is False
    assert (a < (a | b)) is True


def test_the_complement_applies_demorgans_law(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a2 = definitions.parse('A2')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b11 = definitions.parse('B11')
    b2 = definitions.parse('B2')
    bx = definitions.parse('BX')
    universe = definitions.universe
    empty = definitions.empty

    assert str(~a) == "~'A'"
    assert str(~a1) == "~'A1'"
    assert str(~b) == "~'B'"
    assert str(~universe) == "~*"
    assert str(~empty) == "*"

    assert str(~(a & b)) == "~'A' | ~'B'"
    assert str(~(a | b)) == "~'A' & ~'B'"
    assert str(~a & ~a1) == "~'A'"

    assert str(a | ~a) == "*"
    assert str(~a | ~a1) == "~'A1'"
    assert str(~(a | a1)) == "~'A'"
    assert ~(a | a1) == ~a & ~a1
    assert str(~(a & a1)) == "~'A1'"
    assert ~(a & a1) == ~a | ~a1
    assert str(~(~b1 & ~b2)) == "'B1' | 'B2'"

    assert str(a & ~a) == "~*"
    assert str(a & ~a1) == "'A' & ~'A1'"
    assert str(~a & a) == "~*"
    assert str(~a & a1) == "~*"
    assert str(~a1 & a) == "'A' & ~'A1'"
    assert str(b11 & ~bx) == "'B11'"
    assert str(~b1 & bx) == "'BX'"
    assert str(~b11 & bx) == "'BX'"

    assert str(~((a & b1) | b2)) == "(~'A' & ~'B2') | (~'B1' & ~'B2')"
    assert str(~(a | (b1 & b2))) == "(~'A' & ~'B1') | (~'A' & ~'B2')"
    assert str(~(a | (b2 & b1))) == "(~'A' & ~'B1') | (~'A' & ~'B2')"
    assert str(~((a1 & a2) | (b1 & b2))) == (
        "(~'A1' & ~'B1') | (~'A1' & ~'B2') | (~'A2' & ~'B1') | (~'A2' & ~'B2')")
    assert str(~a & ~b2) == "~'A' & ~'B2'"
    assert str(~((a & b) | a1)) == "~'A' | (~'A1' & ~'B')"
    assert str(~(~a | (~a1 & ~b))) == "('A' & 'B') | 'A1'"
    assert str(~~((a & b) | a1)) == "('A' & 'B') | 'A1'"


def test_the_complement_reverses_the_inclusion(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')

    assert (a < a1) is False
    assert (~a < ~a1) is True
    assert (a > a1) is True
    assert (~a > ~a1) is False
    assert (~a1 > ~a) is True
    assert (a < ~a) is False
    assert (a < ~a1) is False
    assert (~a < ~a) is False
    assert (~a < ~a1) is True


def test_the_subset_with_its_negated_superset_is_empty(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    b = definitions.parse('B')

    assert str(~a & (a | b)) == "~'A' & 'B'"
    assert str(a1 & b & ~a) == "~*"
    assert str(a1 & ~a & b) == "~*"
    assert str(~a1 & a & b) == "'A' & ~'A1' & 'B'"


def test_complementary_terms_collapse_into_one(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a11 = definitions.parse('A11')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b2 = definitions.parse('B2')
    universe = definitions.universe
    empty = definitions.empty

    assert str((a | b) & b) == "'B'"
    assert str((a & b) | (a & ~b)) == "'A'"
    assert str((a & b1 & b2) | (a & b1 & ~b2)) == "'A' & 'B1'"
    assert str((a & ~b2 & b1) | (a & b1 & b2)) == "'A' & 'B1'"
    assert str((a & b1 & ~b2) | (a & ~b1 & b2)) == "('A' & 'B1' & ~'B2') | ('A' & ~'B1' & 'B2')"
    assert str(((b2 & a1) | (b2 & a1 & a11)) | ((b2 & a11) | (~b2 & a1) | (~b2 & a1 & a11))) == "'A1'"
    assert str(~(((b2 & a1) | (b2 & a1 & a11)) | ((b2 & a11) | (~b2 & a1) | (~b2 & a1 & a11)))) == "~'A1'"
    assert str(~((~a & b) | (a & b) | (a & ~b))) == "~'A' & ~'B'"
    assert str((~a & ~b2) & (b1 | b2)) == "~'A' & 'B1' & ~'B2'"
    assert str((~a & ~b2) & ~(~b1 & ~b2)) == "~'A' & 'B1' & ~'B2'"
    assert str(~a & ~b2 & universe) == "~'A' & ~'B2'"
    assert str((~a & ~b2 & universe) & ~(~b1 & ~b2)) == "~'A' & 'B1' & ~'B2'"
    assert str((~a & ~b2 & empty) & ~(~b1 & ~b2)) == "~*"
    assert str((~a & ~b2) & ~(~b1 & ~b2 & empty)) == "~'A' & ~'B2'"
    assert str((~a & b1 & a) & b) == "~*"


def test_two_disjoint_sets_never_intersect(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a11 = definitions.parse('A11')
    a1b1 = definitions.parse('A1B1')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b11 = definitions.parse('B11')
    e = definitions.parse('E')
    e1 = definitions.parse('E1')

    assert (a <= e) is False
    assert (a >= e) is False
    assert (a <= ~e) is True
    assert (a >= ~e) is False
    assert (a11 <= ~e) is True
    assert (a11 >= ~e) is False
    assert (~a >= e) is True
    assert (~a11 >= e) is True
    assert (~a >= ~e) is False
    assert (~a11 >= ~e) is False
    assert (a <= e1) is False
    assert (a >= e1) is False
    assert (a <= ~e1) is True
    assert (a >= ~e1) is False
    assert (a11 <= ~e1) is True
    assert (a11 >= ~e1) is False
    assert (~a >= e1) is True
    assert (~a11 >= e1) is True
    assert (~a >= ~e1) is False
    assert (~a <= ~e1) is False
    assert (~a11 >= ~e1) is False

    assert str(b11 & ~e) == "'B11'"
    assert str(~a11 | e) == "~'A11'"
    assert str(~(a1 & a11 & ~e)) == "~'A11'"
    assert str(b1 & e) == "~*"
    assert str(b11 & e) == "~*"
    assert str(b1 | e) == "'B1' | 'E'"
    assert str((b1 & e) | a1b1) == "'A1B1'"
    assert str(a1 & a11 & ~e) == "'A11'"
    assert str(~e & (e | b)) == "'B'"
    assert str((~e & e) | b) == "'B'"


def test_a_huge_combination_reduces_to_its_two_terms(definitions):
    a1 = definitions.parse('A1')
    a11 = definitions.parse('A11')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b2 = definitions.parse('B2')
    a1b1 = definitions.parse('A1B1')
    c = definitions.parse('C')
    d = definitions.parse('D')
    e = definitions.parse('E')

    z1 = c | b2 | a1 | a11
    z2 = (c) | (c & b2) | (c & b2 & a1) | (c & b2 & a11) | (c & ~b2) | (c & ~b2 & a1)
    z3 = (c & ~b2 & a11) | (c & a1) | (c & a1 & b1) | (c & a11) | (c & a11 & b1) | (c & b1)
    z4 = (b2 & a1) | (b2 & a1 & a11) | (b2 & a11) | (~b2 & a1) | (~b2 & a1 & a11)
    z5 = (~b2 & a11) | (a1) | (a1 & a11) | (a1 & a11 & b1) | (a1 & b1) | (a11) | (a11 & b1)
    group1 = z1 & (z2 | z3 | z4 | z5)

    assert str(group1) == "'A1' | 'C'"
    assert str(~group1) == "~'A1' & ~'C'"
    assert str(~~group1) == "'A1' | 'C'"
    assert str((~group1).invert_intersect(~a1)) == "~'C'"

    assert str(group1 & b) == "('A1' & 'B') | ('B' & 'C')"
    assert str(~(group1 & b)) == "(~'A1' & ~'C') | ~'B'"
    assert str(~~(group1 & b)) == "('A1' & 'B') | ('B' & 'C')"
    assert str((group1 & b).invert_intersect(b)) == "'A1' | 'C'"

    assert not (group1 & b).invert_intersect(a1)

    assert str(a1 & d) == "~*"
    assert str(group1 & (c | b | d)) == "('A1' & 'B') | 'C'"
    assert str(~(group1 & (c | b | d))) == "(~'A1' & ~'C') | (~'B' & ~'C')"

    group2 = (b1 | d) & (a1b1 | (a1b1 & d) | (a1b1 & d & e) | (a1b1 & e) | e)
    assert str(group2) == "'A1B1'"


def test_invert_intersect_undoes_the_intersection(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a11 = definitions.parse('A11')
    a2 = definitions.parse('A2')
    a21 = definitions.parse('A21')
    a22 = definitions.parse('A22')
    b = definitions.parse('B')
    b1 = definitions.parse('B1')
    b2 = definitions.parse('B2')
    d = definitions.parse('D')

    assert str((a1 & a2).invert_intersect(a2)) == "'A1'"
    assert str((a1 & b1 | a1 & b2).invert_intersect(a1)) == "'B1' | 'B2'"
    assert str((a1 & b1 | a1 & b2 | a1 & a2).invert_intersect(a1)) == "'A2' | 'B1' | 'B2'"
    assert str((a1 & b1 | a2 & b1).invert_intersect(a1 | a2)) == "'B1'"
    assert str((a1 & b1 | a1 & b2 | a2 & b1 | a2 & b2).invert_intersect(a1 | a2)) == "'B1' | 'B2'"
    assert a.invert_intersect(a | b) is None
    assert a.invert_intersect(a1 | a2) is None
    assert a.invert_intersect(a | d) is None

    cases = [
        (a2, a1),
        (b1 | b2, a1),
        (a2 | b1 | b2, a1),
        (b1, a1 | a2),
        (b1 | b2, a1 | a2),
        (b1 & b2, a1),
        (a2 & b1 & b2, a1),
        (b1 & b2, a1 | a2),
        (a1, b1 & b2),
        (a1 | a2, b1 & b2),
        (a1, a2 | b1 & b2),
        (a11 | a21, a22 | b1 & b2),
        (a11 & a21, a22 | b1 & b2),
        (a, a1 | b),
        (a1 | b, a),
    ]
    for left, right in cases:
        assert str((left & right).invert_intersect(right)) == str(left), (
            f'debería poder invertir la intersección: {left & right}\npor: ({right})')


def test_matches_asks_whether_the_ids_satisfy_the_expression(definitions):
    a = definitions.parse('A')
    a1 = definitions.parse('A1')
    a11 = definitions.parse('A11')
    b = definitions.parse('B')
    c = definitions.parse('C')
    d = definitions.parse('D')

    matching = [
        (a, {1, 13}),
        (a, {1, 2, 3, 13}),
        (a1, {1, 2, 13}),
        (a11, {1, 2, 3, 13}),
        (a | b, {1, 13}),
        (b | c, {1, 13}),
        (a1 | b, {1, 2, 13}),
        (a11 | b, {1, 2, 3, 13}),
        ((a11 | b) & ~d, {1, 2, 3, 13}),
        (a & ~a11, {1, 13}),
        (a & ~a11, {1, 2, 13}),
    ]
    for spec, group_ids in matching:
        assert spec.matches(group_ids), (
            f'un usuario con los grupos {definitions.from_ids(group_ids, keep_subsets=True)} '
            f'debería satisfacer {spec}')

    non_matching = [
        (a, {13}),
        (a1, {13}),
        (a11, {13}),
        (a | b, {13}),
        (a & ~c, {13}),
        (a & ~b & ~c, {13}),
        ((a11 | b) & ~c, {1, 2, 3, 13}),
        (a & ~a11, {1, 2, 3, 13}),
    ]
    for spec, group_ids in non_matching:
        assert not spec.matches(group_ids), (
            f'un usuario con los grupos {definitions.from_ids(group_ids, keep_subsets=True)} '
            f'no debería satisfacer {spec}')


def test_an_unknown_reference_still_composes(definitions):
    a = definitions.parse('A')
    u1 = definitions.parse('unknown.group1', raise_if_not_found=False)
    u2 = definitions.parse('unknown.group2', raise_if_not_found=False)

    assert u1 == u1
    assert u1 != u2

    assert a | u1 == u1 | a
    assert u1 | u2 == u2 | u1
    assert a & u1 == u1 & a
    assert u1 & u2 == u2 & u1

    assert a | u1 | u2 == a | u1 | u2
    assert a | u2 | u1 == a | u1 | u2
    assert u1 | a | u2 == a | u1 | u2
    assert u2 | a | u1 == a | u1 | u2
    assert u2 | u1 | a == a | u1 | u2

    assert a & u1 & u2 == a & u1 & u2
    assert a & u2 & u1 == a & u1 & u2
    assert u1 & a & u2 == a & u1 & u2
    assert u2 & a & u1 == a & u1 & u2
    assert u2 & u1 & a == a & u1 & u2


def test_an_unknown_reference_raises_when_asked_to(definitions):
    with pytest.raises(KeyError):
        definitions.parse('unknown.group1')


def test_the_key_round_trips_through_from_key(definitions):
    a = definitions.parse('A')
    b = definitions.parse('B')
    c = definitions.parse('C')
    u = definitions.parse('unknown.group', raise_if_not_found=False)

    cases = [
        a,
        a | b,
        a & b,
        a & ~b,
        (a | b) & ~c,
        u,
        a | u | b,
    ]

    for groups in cases:
        assert isinstance(groups.key, str)
        rebuilt = definitions.from_key(groups.key)
        assert rebuilt == groups
        assert rebuilt.key == groups.key


# -- los tres accesores del ejemplo del docstring del módulo -----------------

@pytest.fixture(scope='module')
def numbers():
    """El ejemplo del docstring de ``SetDefinitions.__init__``, verbatim."""
    return SetDefinitions({
        1: {'ref': 'N', 'supersets': [2]},
        2: {'ref': 'Z', 'supersets': [3]},
        3: {'ref': 'Q', 'supersets': [4]},
        4: {'ref': 'R', 'supersets': [6]},
        5: {'ref': 'I', 'supersets': [6], 'disjoints': [4]},
        6: {'ref': 'C'},
        7: {'ref': 'R\\Q', 'supersets': [4]},
    })


def test_get_superset_ids_climbs_the_transitive_closure(numbers):
    # "Los supraconjuntos de Q (id 3) son R y C, con ids [4, 6]" — docstring.
    assert numbers.get_superset_ids([3]) == [4, 6]


def test_get_subset_ids_descends_the_transitive_closure(numbers):
    # "Los subconjuntos de Q (id 3) son Z y N, con ids [1, 2]" — docstring.
    assert numbers.get_subset_ids([3]) == [1, 2]


def test_get_disjoint_ids_returns_only_what_an_edge_declares(numbers):
    """El disjunto de Q es I, y **no** R\\Q — pese a lo que dice la fuente.

    El docstring de ``odoo19c`` afirma ``[7, 5]``. Medido contra la propia
    referencia con ese mismo ejemplo: devuelve ``[5]``. R\\Q (7) se declara
    subconjunto de R, nunca disjunto de Q, así que no hay arista de disjunción
    que la clausura pueda propagar. Este caso fija la conducta medida, no la
    documentada.
    """
    assert numbers.get_disjoint_ids([3]) == [5]
    # El control que discrimina: I (5) sí declara la arista, contra R (4), y
    # por eso su clausura alcanza a todo lo que hay bajo R.
    assert numbers.get_disjoint_ids([5]) == [1, 2, 3, 4, 7]


def test_get_id_resolves_the_reference_and_the_universal_set(numbers):
    assert numbers.get_id('Q') == 3
    assert numbers.get_id('*') == '*'
    assert numbers.get_id('no-existe') is None


def test_from_ids_keeps_the_most_specific_set_of_each_chain(numbers):
    """``keep_subsets`` se queda con el **menor** de la cadena, no con el mayor.

    N <= Z <= Q: quien pertenece a N ya pertenece a Z y a Q por implicación,
    así que el que informa es N. El filtro descarta la hoja que tenga algún
    otro subconjunto suyo dentro del propio conjunto de ids.
    """
    assert str(numbers.from_ids([1, 2, 3], keep_subsets=True)) == "'N'"
    # Sin ninguna cadena entre ellos, ninguno se descarta. El orden lo fija
    # la clave de la intersección, que es el id — no el nombre.
    assert str(numbers.from_ids([1, 5], keep_subsets=True)) == "'N' | 'I'"
    # Y el contraste que da sentido al filtro: **sin** él la unión colapsa
    # al revés, al más general — porque absorbe a sus subconjuntos.
    assert str(numbers.from_ids([1, 2, 3])) == "'Q'"
