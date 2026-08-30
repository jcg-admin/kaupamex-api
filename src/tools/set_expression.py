"""``tools.set_expression`` — espejo de ``odoo/tools/set_expression.py`` (Odoo 19).

Álgebra de conjuntos con nombre: unión, intersección y complemento sobre una
colección de conjuntos declarados por id, con sus supraconjuntos y sus
conjuntos disjuntos. Es el mecanismo con el que la referencia expresa
"pertenece al grupo A **y** no al grupo B" sin evaluar nada contra la base:
la expresión se construye, se simplifica y se compara, y sólo al final se
pregunta si un conjunto de ids de grupo la satisface (``matches``).

**Se porta verbatim porque el stack no trae nada equivalente.** ``set`` de
Python representa un conjunto **extensional** —sus elementos— y aquí hace
falta uno **intensional**: la expresión ``A & ~B`` no enumera nada, y su
simplificación depende de las relaciones declaradas (``A1 <= A`` implica
``A1 & ~A == ∅``). ``Q`` de Django compone predicados de consulta, no
conjuntos: no sabe reducir, no compara por inclusión y no tiene complemento
con álgebra de disjuntos.

Quién lo consume aquí:

- ``ResGroups._get_group_definitions`` — construye el ``SetDefinitions`` del
  registro de grupos, con sus implicaciones y sus disjuntos.
- ``IrModelAccess._get_access_groups`` — devuelve ``empty`` / ``universe`` /
  ``from_ids(...)`` según qué grupos tengan el permiso pedido.
- ``ResUsers`` — resuelve el id de un grupo por su referencia (``get_id``).

Adaptado de Odoo Community ``odoo/tools/set_expression.py`` (LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

**Única divergencia de forma:** la fuente importa ``Collection`` e
``Iterable`` dentro de ``if typing.TYPE_CHECKING:``. Aquí van al top del
módulo — ``no-lazy-imports.md`` prohíbe el ``import`` dentro de un bloque
condicional, y ``collections.abc`` es stdlib sin coste de arranque.
"""
from __future__ import annotations

import ast
import typing
from abc import ABC, abstractmethod
from collections.abc import Collection, Iterable

__all__ = ['SetDefinitions', 'SetExpression']


class SetDefinitions:
    """Colección de definiciones de conjunto.

    Cada conjunto queda definido por un id, un nombre, sus supraconjuntos y
    los conjuntos disjuntos con él. Este objeto es la **fábrica** de las
    expresiones de conjunto: combinaciones de conjuntos con nombre mediante
    unión, intersección y complemento.
    """
    __slots__ = ('__leaves',)

    def __init__(self, definitions: dict[int, dict]):
        """Inicializa el objeto con ``definitions``.

        ``definitions`` mapea cada id de conjunto a un dict con las claves
        opcionales ``"ref"`` (el nombre del conjunto), ``"supersets"`` (una
        colección de ids) y ``"disjoints"`` (otra colección de ids).

        Ejemplo de definiciones, con los naturales (N), los enteros (Z), los
        racionales (Q), los irracionales (R\\Q), los reales (R), los
        imaginarios (I) y los complejos (C)::

            {
                1: {"ref": "N", "supersets": [2]},
                2: {"ref": "Z", "supersets": [3]},
                3: {"ref": "Q", "supersets": [4]},
                4: {"ref": "R", "supersets": [6]},
                5: {"ref": "I", "supersets": [6], "disjoints": [4]},
                6: {"ref": "C"},
                7: {"ref": "R\\Q", "supersets": [4]},
            }
            Representación:
            ┌──────────────────────────────────────────┐
            │ C  ┌──────────────────────────┐          │
            │    │ R  ┌───────────────────┐ │ ┌──────┐ |   "C"
            │    │    │ Q  ┌────────────┐ │ │ │ I    | |   "I" implica "C"
            │    │    │    │ Z  ┌─────┐ │ │ │ │      | |   "R" implica "C"
            │    │    │    │    │ N   │ │ │ │ │      │ │   "Q" implica "R"
            │    │    │    │    └─────┘ │ │ │ │      │ │   "R\\Q" implica "R"
            │    │    │    └────────────┘ │ │ │      │ │   "Z" implica "Q"
            │    │    └───────────────────┘ │ │      │ │   "N" implica "Z"
            │    │      ┌───────────────┐   │ │      │ │
            │    │      │ R\\Q          │   │ │      │ │
            │    │      └───────────────┘   │ └──────┘ │
            │    └──────────────────────────┘          │
            └──────────────────────────────────────────┘
        """
        self.__leaves: dict[int | str, Leaf] = {}

        for leaf_id, info in definitions.items():
            ref = info['ref']
            assert ref != '*', "La referencia de conjunto '*' está reservada para el conjunto universal."
            leaf = Leaf(leaf_id, ref)
            self.__leaves[leaf_id] = leaf
            self.__leaves[ref] = leaf

        # clausura transitiva de subconjuntos y supraconjuntos
        subsets = {leaf.id: leaf.subsets for leaf in self.__leaves.values()}
        supersets = {leaf.id: leaf.supersets for leaf in self.__leaves.values()}
        for leaf_id, info in definitions.items():
            for greater_id in info.get('supersets', ()):
                # transitividad: smaller_ids <= leaf_id <= greater_id <= greater_ids
                smaller_ids = subsets[leaf_id]
                greater_ids = supersets[greater_id]
                for smaller_id in smaller_ids:
                    supersets[smaller_id].update(greater_ids)
                for greater_id in greater_ids:
                    subsets[greater_id].update(smaller_ids)

        # clausura transitiva de la relación de disjunción
        disjoints = {leaf.id: leaf.disjoints for leaf in self.__leaves.values()}
        for leaf_id, info in definitions.items():
            for distinct_id in info.get('disjoints', set()):
                # todo subsets[leaf_id] es disjunto de todo subsets[distinct_id]
                left_ids = subsets[leaf_id]
                right_ids = subsets[distinct_id]
                for left_id in left_ids:
                    disjoints[left_id].update(right_ids)
                for right_id in right_ids:
                    disjoints[right_id].update(left_ids)

    @property
    def empty(self) -> SetExpression:
        """El conjunto vacío."""
        return EMPTY_UNION

    @property
    def universe(self) -> SetExpression:
        """El conjunto universal."""
        return UNIVERSAL_UNION

    def parse(self, refs: str, raise_if_not_found: bool = True) -> SetExpression:
        """Devuelve la expresión de conjunto correspondiente a ``refs``.

        :param str refs: lista de referencias de conjunto separadas por coma,
            cada una opcionalmente precedida de ``!`` (ítem negativo). El
            resultado es la unión de los ítems positivos, cada uno
            intersecado con todos los negativos
            (p. ej. ``base.group_user,base.group_portal,!base.group_system``).
        """
        positives: list[Leaf] = []
        negatives: list[Leaf] = []
        for xmlid in refs.split(','):
            if xmlid.startswith('!'):
                negatives.append(~self.__get_leaf(xmlid[1:], raise_if_not_found))
            else:
                positives.append(self.__get_leaf(xmlid, raise_if_not_found))

        if positives:
            return Union(Inter([leaf] + negatives) for leaf in positives)
        else:
            return Union([Inter(negatives)])

    def from_ids(self, ids: Iterable[int], keep_subsets: bool = False) -> SetExpression:
        """Devuelve la expresión de conjunto correspondiente a los ids dados."""
        if keep_subsets:
            ids = set(ids)
            ids = [leaf_id for leaf_id in ids if not any((self.__leaves[leaf_id].subsets - {leaf_id}) & ids)]
        return Union(Inter([self.__leaves[leaf_id]]) for leaf_id in ids)

    def from_key(self, key: str) -> SetExpression:
        """Devuelve la expresión de conjunto correspondiente a la clave dada."""
        # union_tuple = tuple(tuple(tuple(leaf_id, negative), ...), ...)
        union_tuple = ast.literal_eval(key)
        return Union([
            Inter([
                ~leaf if negative else leaf
                for leaf_id, negative in inter_tuple
                for leaf in [self.__get_leaf(leaf_id, raise_if_not_found=False)]
            ], optimal=True)
            for inter_tuple in union_tuple
        ], optimal=True)

    def get_id(self, ref: LeafIdType) -> LeafIdType | None:
        """Devuelve el id de un conjunto por su referencia, o ``None`` si no existe."""
        if ref == '*':
            return UNIVERSAL_LEAF.id
        leaf = self.__leaves.get(ref)
        return None if leaf is None else leaf.id

    def __get_leaf(self, ref: str | int, raise_if_not_found: bool = True) -> Leaf:
        """Devuelve el objeto de grupo a partir de su referencia.

        :param ref: la referencia de una hoja.
        """
        if ref == '*':
            return UNIVERSAL_LEAF
        if not raise_if_not_found and ref not in self.__leaves:
            return Leaf(UnknownId(ref), ref)
        return self.__leaves[ref]

    def get_superset_ids(self, ids: Iterable[int]) -> list[int]:
        """Devuelve los supraconjuntos de la lista de ids dada.

        Con el ejemplo declarado en el constructor: los supraconjuntos de "Q"
        (id 3) son "R" y "C", con ids [4, 6].
        """
        return sorted({
            sup_id
            for id_ in ids
            if id_ in self.__leaves
            for sup_id in self.__leaves[id_].supersets
            if sup_id != id_
        })

    def get_subset_ids(self, ids: Iterable[int]) -> list[int]:
        """Devuelve los subconjuntos de la lista de ids dada.

        Con el ejemplo declarado en el constructor: los subconjuntos de "Q"
        (id 3) son "Z" y "N", con ids [1, 2].
        """
        return sorted({
            sub_id
            for id_ in ids
            if id_ in self.__leaves
            for sub_id in self.__leaves[id_].subsets
            if sub_id != id_
        })

    def get_disjoint_ids(self, ids: Iterable[int]) -> list[int]:
        """Devuelve los conjuntos disjuntos de la lista de ids dada.

        Con el ejemplo declarado en el constructor: el conjunto disjunto de
        "Q" (id 3) es "I", con id 5.

        **Corregido respecto de la fuente.** Su docstring dice *"is "R\\Q" and
        "I" with ids [7, 5]"*, y ninguna de las dos implementaciones devuelve
        el 7: medido contra ``odoo19c`` con ese mismo ejemplo, ambas dan
        ``[5]``. "R\\Q" se declara **subconjunto** de R, nunca disjunto de Q,
        así que no hay arista que la clausura pueda propagar. Se corrige el
        texto en vez de copiarlo: un docstring que afirma lo que el código no
        hace propaga el error a quien lo lea.
        """
        return sorted({
            disjoint_id
            for id_ in ids
            if id_ in self.__leaves
            for disjoint_id in self.__leaves[id_].disjoints
        })


class SetExpression(ABC):
    """Combinación de conjuntos con nombre por unión, intersección y complemento."""

    @abstractmethod
    def is_empty(self) -> bool:
        """Devuelve si ``self`` es el conjunto vacío, el que no contiene nada."""
        raise NotImplementedError()

    @abstractmethod
    def is_universal(self) -> bool:
        """Devuelve si ``self`` es el conjunto universal, el que contiene todo."""
        raise NotImplementedError()

    @abstractmethod
    def invert_intersect(self, factor: SetExpression) -> SetExpression | None:
        """Operación inversa de la intersección (una suerte de factorización).

        Tal que ``self == result & factor``.
        """
        raise NotImplementedError()

    @abstractmethod
    def matches(self, user_group_ids: Iterable[int]) -> bool:
        """Devuelve si los ids de grupo dados están incluidos en ``self``."""
        raise NotImplementedError()

    @property
    @abstractmethod
    def key(self) -> str:
        """Devuelve un identificador único de la expresión."""
        raise NotImplementedError()

    @abstractmethod
    def __and__(self, other: SetExpression) -> SetExpression:
        raise NotImplementedError()

    @abstractmethod
    def __or__(self, other: SetExpression) -> SetExpression:
        raise NotImplementedError()

    @abstractmethod
    def __invert__(self) -> SetExpression:
        raise NotImplementedError()

    @abstractmethod
    def __eq__(self, other) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def __le__(self, other: SetExpression) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def __lt__(self, other: SetExpression) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def __hash__(self):
        raise NotImplementedError()


class Union(SetExpression):
    """Implementación de una expresión de conjunto.

    La representa como una unión de intersecciones de conjuntos con nombre o
    de su complemento.
    """

    def __init__(self, inters: Iterable[Inter] = (), optimal=False):
        if inters and not optimal:
            inters = self.__combine((), inters)
        self.__inters = sorted(inters, key=lambda inter: inter.key)
        self.__key = str(tuple(inter.key for inter in self.__inters))
        self.__hash = hash(self.__key)

    @property
    def key(self) -> str:
        return self.__key

    @staticmethod
    def __combine(inters: Iterable[Inter], inters_to_add: Iterable[Inter]) -> list[Inter]:
        """Combina una unión de intersecciones existente con intersecciones extra."""
        result = list(inters)

        todo = list(inters_to_add)
        while todo:
            inter_to_add = todo.pop()
            if inter_to_add.is_universal():
                return [UNIVERSAL_INTER]
            if inter_to_add.is_empty():
                continue

            for index, inter in enumerate(result):
                merged = inter._union_merge(inter_to_add)
                if merged is not None:
                    result.pop(index)
                    todo.append(merged)
                    break
            else:
                result.append(inter_to_add)

        return result

    def is_empty(self) -> bool:
        """Devuelve si ``self`` es el conjunto vacío, el que no contiene nada."""
        return not self.__inters

    def is_universal(self) -> bool:
        """Devuelve si ``self`` es el conjunto universal, el que contiene todo."""
        return any(item.is_universal() for item in self.__inters)

    def invert_intersect(self, factor: SetExpression) -> Union | None:
        """Operación inversa de la intersección (una suerte de factorización).

        Tal que ``self == result & factor``.
        """
        if factor == self:
            return UNIVERSAL_UNION

        rfactor = ~factor
        if rfactor.is_empty() or rfactor.is_universal():
            return None
        rself = ~self

        assert isinstance(rfactor, Union)
        inters = [inter for inter in rself.__inters if inter not in rfactor.__inters]
        if len(rself.__inters) - len(inters) != len(rfactor.__inters):
            # no es posible invertir la intersección
            return None

        rself_value = Union(inters)
        return ~rself_value

    def __and__(self, other: SetExpression) -> Union:
        assert isinstance(other, Union)
        if self.is_universal():
            return other
        if other.is_universal():
            return self
        if self.is_empty() or other.is_empty():
            return EMPTY_UNION
        if self == other:
            return self
        return Union(
            self_inter & other_inter
            for self_inter in self.__inters
            for other_inter in other.__inters
        )

    def __or__(self, other: SetExpression) -> Union:
        assert isinstance(other, Union)
        if self.is_empty():
            return other
        if other.is_empty():
            return self
        if self.is_universal() or other.is_universal():
            return UNIVERSAL_UNION
        if self == other:
            return self
        inters = self.__combine(self.__inters, other.__inters)
        return Union(inters, optimal=True)

    def __invert__(self) -> Union:
        if self.is_empty():
            return UNIVERSAL_UNION
        if self.is_universal():
            return EMPTY_UNION

        # se aplican las leyes de De Morgan
        inverses_of_inters = [
            # ~(A & B) = ~A | ~B
            Union(Inter([~leaf]) for leaf in inter.leaves)
            for inter in self.__inters
        ]
        result = inverses_of_inters[0]
        # ~(A | B) = ~A & ~B
        for inverse in inverses_of_inters[1:]:
            result = result & inverse

        return result

    def matches(self, user_group_ids) -> bool:
        if self.is_empty() or not user_group_ids:
            return False
        if self.is_universal():
            return True
        user_group_ids = set(user_group_ids)
        return any(inter.matches(user_group_ids) for inter in self.__inters)

    def __bool__(self):
        raise NotImplementedError()

    def __eq__(self, other) -> bool:
        return isinstance(other, Union) and self.__key == other.__key

    def __le__(self, other: SetExpression) -> bool:
        if not isinstance(other, Union):
            return False
        if self.__key == other.__key:
            return True
        if self.is_universal() or other.is_empty():
            return False
        if other.is_universal() or self.is_empty():
            return True
        return all(
            any(self_inter <= other_inter for other_inter in other.__inters)
            for self_inter in self.__inters
        )

    def __lt__(self, other: SetExpression) -> bool:
        return self != other and self.__le__(other)

    def __str__(self):
        """Representación como unión de intersecciones, con referencias legibles.

        P. ej. ``('base.group_user' & 'base.group_multi_company') |
        ('base.group_portal' & ~'base.group_multi_company') |
        'base.group_public'``.
        """
        if self.is_empty():
            return "~*"

        def leaf_to_str(leaf):
            return f"{'~' if leaf.negative else ''}{leaf.ref!r}"

        def inter_to_str(inter, wrapped=False):
            result = " & ".join(leaf_to_str(leaf) for leaf in inter.leaves) or "*"
            return f"({result})" if wrapped and len(inter.leaves) > 1 else result

        wrapped = len(self.__inters) > 1
        return " | ".join(inter_to_str(inter, wrapped) for inter in self.__inters)

    def __repr__(self):
        return repr(self.__str__())

    def __hash__(self):
        return self.__hash


class Inter:
    """Parte de la implementación de una expresión de conjunto.

    Representa una intersección de conjuntos con nombre o de su complemento.
    """
    __slots__ = ('key', 'leaves')

    def __init__(self, leaves: Iterable[Leaf] = (), optimal=False):
        if leaves and not optimal:
            leaves = self.__combine((), leaves)
        self.leaves: list[Leaf] = sorted(leaves, key=lambda leaf: leaf.key)
        self.key: tuple[tuple[LeafIdType, bool], ...] = tuple(leaf.key for leaf in self.leaves)

    @staticmethod
    def __combine(leaves: Iterable[Leaf], leaves_to_add: Iterable[Leaf]) -> list[Leaf]:
        """Combina una intersección de hojas existente con hojas extra."""
        result = list(leaves)
        for leaf_to_add in leaves_to_add:
            for index, leaf in enumerate(result):
                if leaf.isdisjoint(leaf_to_add):  # leaf & leaf_to_add = vacío
                    return [EMPTY_LEAF]
                if leaf <= leaf_to_add:  # leaf & leaf_to_add = leaf
                    break
                if leaf_to_add <= leaf:  # leaf & leaf_to_add = leaf_to_add
                    result[index] = leaf_to_add
                    break
            else:
                if not leaf_to_add.is_universal():
                    result.append(leaf_to_add)
        return result

    def is_empty(self) -> bool:
        """Devuelve si ``self`` es el conjunto vacío."""
        return any(item.is_empty() for item in self.leaves)

    def is_universal(self) -> bool:
        """Devuelve si ``self`` es el conjunto universal, el que contiene todo."""
        return not self.leaves

    def matches(self, user_group_ids) -> bool:
        """Devuelve si los ids de grupo dados están incluidos en ``self``."""
        return all(leaf.matches(user_group_ids) for leaf in self.leaves)

    def _union_merge(self, other: Inter) -> Inter | None:
        """Unión de ``self`` con otra intersección, si es representable como intersección.

        Devuelve ``None`` en caso contrario.
        """
        # cubre casos como (A & B) | A -> A
        if self.is_universal() or other <= self:
            return self
        if self <= other:
            return other

        # combina las partes complementarias: (A & ~B) | (A & B) -> A
        if len(self.leaves) == len(other.leaves):
            opposite_index = None
            # se aprovecha que las hojas están ordenadas
            for index, self_leaf, other_leaf in zip(range(len(self.leaves)), self.leaves, other.leaves):
                if self_leaf.id != other_leaf.id:
                    return None
                if self_leaf.negative != other_leaf.negative:
                    if opposite_index is not None:
                        return None  # ya hay dos hojas opuestas
                    opposite_index = index
            if opposite_index is not None:
                leaves = list(self.leaves)
                leaves.pop(opposite_index)
                return Inter(leaves, optimal=True)
        return None

    def __and__(self, other: Inter) -> Inter:
        if self.is_empty() or other.is_empty():
            return EMPTY_INTER
        if self.is_universal():
            return other
        if other.is_universal():
            return self
        leaves = self.__combine(self.leaves, other.leaves)
        return Inter(leaves, optimal=True)

    def __eq__(self, other) -> bool:
        return isinstance(other, Inter) and self.key == other.key

    def __le__(self, other: Inter) -> bool:
        return self.key == other.key or all(
            any(self_leaf <= other_leaf for self_leaf in self.leaves)
            for other_leaf in other.leaves
        )

    def __lt__(self, other: Inter) -> bool:
        return self != other and self <= other

    def __hash__(self):
        return hash(self.key)


class Leaf:
    """Parte de la implementación de una expresión de conjunto.

    Representa un conjunto con nombre o su complemento.
    """
    __slots__ = ('disjoints', 'id', 'inverse', 'key', 'negative', 'ref', 'subsets', 'supersets')

    def __init__(self, leaf_id: LeafIdType, ref: str | int | None = None, negative: bool = False):
        self.id = leaf_id
        self.ref = ref or str(leaf_id)
        self.negative = bool(negative)
        self.key: tuple[LeafIdType, bool] = (leaf_id, self.negative)

        self.subsets: set[LeafIdType] = {leaf_id}       # todos los ids de hoja que son <= self
        self.supersets: set[LeafIdType] = {leaf_id}     # todos los ids de hoja que son >= self
        self.disjoints: set[LeafIdType] = set()         # todos los ids de hoja disjuntos de self
        self.inverse: Leaf | None = None

    def __invert__(self) -> Leaf:
        if self.inverse is None:
            self.inverse = Leaf(self.id, self.ref, negative=not self.negative)
            self.inverse.inverse = self
            self.inverse.subsets = self.subsets
            self.inverse.supersets = self.supersets
            self.inverse.disjoints = self.disjoints
        return self.inverse

    def is_empty(self) -> bool:
        """Devuelve si ``self`` es el conjunto vacío."""
        return self.ref == '*' and self.negative

    def is_universal(self) -> bool:
        """Devuelve si ``self`` es el conjunto universal."""
        return self.ref == '*' and not self.negative

    def isdisjoint(self, other: Leaf) -> bool:
        """Devuelve si ``self`` y ``other`` no comparten ningún elemento."""
        if self.negative:
            return other <= ~self
        elif other.negative:
            return self <= ~other
        else:
            return self.id in other.disjoints

    def matches(self, user_group_ids: Collection[int]) -> bool:
        """Devuelve si los ids de grupo dados están incluidos en ``self``."""
        return (self.id not in user_group_ids) if self.negative else (self.id in user_group_ids)

    def __eq__(self, other) -> bool:
        return isinstance(other, Leaf) and self.key == other.key

    def __le__(self, other: Leaf) -> bool:
        if self.is_empty() or other.is_universal():
            return True
        elif self.is_universal() or other.is_empty():
            return False
        elif self.negative:
            return other.negative and ~other <= ~self
        elif other.negative:
            return self.id in other.disjoints
        else:
            return self.id in other.subsets

    def __lt__(self, other: Leaf) -> bool:
        return self != other and self <= other

    def __hash__(self):
        return hash(self.key)


class UnknownId(str):
    """Id especial de las hojas desconocidas.

    Se comporta como estrictamente mayor que cualquier otra clase de id.
    """
    __slots__ = ()

    def __lt__(self, other) -> bool:
        if isinstance(other, UnknownId):
            return super().__lt__(other)
        return False

    def __gt__(self, other) -> bool:
        if isinstance(other, UnknownId):
            return super().__gt__(other)
        return True


LeafIdType = int | typing.Literal["*"] | UnknownId

# constantes
UNIVERSAL_LEAF = Leaf('*')
EMPTY_LEAF = ~UNIVERSAL_LEAF

EMPTY_INTER = Inter([EMPTY_LEAF])
UNIVERSAL_INTER = Inter()

EMPTY_UNION = Union()
UNIVERSAL_UNION = Union([UNIVERSAL_INTER])
