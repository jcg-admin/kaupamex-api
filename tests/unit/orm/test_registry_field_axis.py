"""``Registry`` tramo 2 — el eje de campos y disparadores.

La referencia declara ocho simbolos entre ``field_inverses`` (``odoo19c:
odoo/orm/registry.py:506``) e ``is_modifying_relations`` (``:670``). Este
arbol los tenia como **funciones de modulo** delegando en un
``_TriggerRegistry`` singleton, y ``Registry`` no los exponia: un llamador que
escribiera ``registry.get_dependent_fields(f)`` —la firma de la fuente—
recibia ``AttributeError``.

Dos de los ocho estaban **ausentes** del arbol, no solo del objeto:

- ``_discard_fields`` (``:573``), que retira un campo de las cinco estructuras
  derivadas a la vez;
- las **tres comprobaciones de consistencia** de ``field_computed``
  (``:526-550``) — ``compute_sudo``, ``precompute`` y ``store`` — que avisan
  cuando dos campos comparten metodo de calculo y no comparten esas banderas.

**El control que discrimina** es ``test_a_consistent_group_warns_nothing``:
un grupo coherente NO debe avisar. Sin ese caso, un ``warnings.warn``
incondicional pasaria los tres casos positivos y nadie lo notaria — es el
sub-patron D de ``metrica-decide-la-conclusion.md``. El segundo control es
``test_discarding_an_unknown_field_is_a_no_op``: la fuente usa ``pop(f, None)``
a proposito, porque un campo a medida puede no estar en los mapas.
"""
import warnings

import pytest
from django.apps import apps

from orm.registry import (Registry, TriggerTree, _ComputedGrouper, _triggers,
                          clear_field_depends, field_depends, field_inverses)


@pytest.fixture
def registry():
    """Un registro construido, con su mapa de proceso intacto."""
    Registry.delete_all()
    built = Registry('alfa')
    yield built
    Registry.delete_all()


@pytest.fixture
def partner():
    return apps.get_model('base', 'ResPartner')


class _Field:
    """Un doble de campo: lo que ``field_computed`` mira, y nada mas."""

    def __init__(self, name, compute, *, compute_sudo=False,
                 precompute=False, store=True):
        self.name = name
        self.compute = compute
        self.compute_sudo = compute_sudo
        self.precompute = precompute
        self.store = store


class _Meta:
    def __init__(self, fields):
        self._declared = fields

    def get_fields(self):
        return self._declared


class _Model:
    def __init__(self, name, fields):
        self._name = name
        self._meta = _Meta(fields)


class TestFieldInverses:
    """``registry.field_inverses`` — cada lado de una relacion apunta al otro."""

    def test_the_registry_reads_the_map_of_the_process(self, registry, partner):
        parent = partner._meta.get_field('parent')
        assert registry.field_inverses[parent] == field_inverses[parent]

    def test_both_sides_point_at_each_other(self, registry, partner):
        parent = partner._meta.get_field('parent')
        remote = parent.remote_field
        assert remote in registry.field_inverses[parent]
        assert parent in registry.field_inverses[remote]

    def test_a_field_without_inverse_answers_the_empty_tuple(self, registry, partner):
        """El contrato de ``Collector``: lo ausente devuelve ``()``, no levanta."""
        name = partner._meta.get_field('name')
        assert registry.field_inverses[name] == ()


class TestFieldComputed:
    """``registry.field_computed`` — el grupo que comparte metodo de calculo."""

    def test_a_computed_field_yields_its_whole_group(self, registry, partner):
        commercial = partner._meta.get_field('commercial_partner_id')
        group = registry.field_computed[commercial]
        assert commercial in group
        assert all(f.compute == commercial.compute for f in group)

    def test_a_field_without_compute_is_absent(self, registry, partner):
        """La fuente no lo cubre: consultarlo es un error de programacion."""
        with pytest.raises(KeyError):
            registry.field_computed[partner._meta.get_field('name')]

    def test_a_consistent_group_warns_nothing(self):
        """El control: dos campos coherentes NO avisan.

        Sin este caso un ``warn`` incondicional pasaria los tres positivos.
        """
        model = _Model('x.consistente', [
            _Field('a', '_compute_par', compute_sudo=True, precompute=True, store=True),
            _Field('b', '_compute_par', compute_sudo=True, precompute=True, store=True),
        ])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            _ComputedGrouper()._build([model])
        assert caught == []

    def test_a_lone_field_warns_nothing(self):
        """La fuente salta el grupo de menos de dos (``:524-525``)."""
        model = _Model('x.solo', [_Field('a', '_compute_uno', store=False)])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            _ComputedGrouper()._build([model])
        assert caught == []

    @pytest.mark.parametrize('bandera,esperado', [
        ('compute_sudo', "inconsistent 'compute_sudo'"),
        ('precompute', "inconsistent 'precompute'"),
        ('store', "inconsistent 'store'"),
    ])
    def test_it_warns_when_a_flag_disagrees(self, bandera, esperado):
        primero = _Field('a', '_compute_par')
        segundo = _Field('b', '_compute_par')
        setattr(segundo, bandera, not getattr(primero, bandera))
        model = _Model('x.discorde', [primero, segundo])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            _ComputedGrouper()._build([model])
        mensajes = [str(w.message) for w in caught]
        assert any(esperado in m for m in mensajes), mensajes
        assert any('x.discorde' in m for m in mensajes), mensajes

    def test_the_warning_names_both_fields(self):
        model = _Model('x.discorde', [
            _Field('a', '_compute_par', store=True),
            _Field('b', '_compute_par', store=False),
        ])
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            _ComputedGrouper()._build([model])
        texto = ' '.join(str(w.message) for w in caught)
        assert 'a' in texto and 'b' in texto


class TestFieldTriggers:
    """``registry._field_triggers`` — la inversa de las dependencias."""

    def test_it_is_the_map_of_the_process(self, registry):
        assert registry._field_triggers is _triggers.field_triggers()

    def test_a_dependency_names_the_fields_that_depend_on_it(self, registry, partner):
        is_company = partner._meta.get_field('is_company')
        commercial = partner._meta.get_field('commercial_partner_id')
        assert commercial in registry._field_triggers[is_company][()]


class TestTriggerTreeReaders:
    """``get_field_trigger_tree``, ``get_trigger_tree`` y ``get_dependent_fields``."""

    def test_a_dependency_gets_a_tree_with_its_dependents(self, registry, partner):
        is_company = partner._meta.get_field('is_company')
        tree = registry.get_field_trigger_tree(is_company)
        assert isinstance(tree, TriggerTree)
        assert partner._meta.get_field('commercial_partner_id') in tree.root

    def test_a_field_without_triggers_gets_an_empty_tree(self, registry, partner):
        tree = registry.get_field_trigger_tree(partner._meta.get_field('id'))
        assert isinstance(tree, TriggerTree)
        assert not tree.root and not tree

    def test_the_tree_is_memoised(self, registry, partner):
        is_company = partner._meta.get_field('is_company')
        assert (registry.get_field_trigger_tree(is_company)
                is registry.get_field_trigger_tree(is_company))

    def test_get_trigger_tree_merges_what_changed(self, registry, partner):
        is_company = partner._meta.get_field('is_company')
        company_name = partner._meta.get_field('company_name')
        merged = registry.get_trigger_tree([is_company, company_name])
        assert partner._meta.get_field('commercial_partner_id') in merged.root
        assert partner._meta.get_field('commercial_company_name') in merged.root

    def test_select_drops_what_it_refuses(self, registry, partner):
        """El control de ``select``: con un predicado falso el arbol queda vacio."""
        is_company = partner._meta.get_field('is_company')
        merged = registry.get_trigger_tree([is_company], select=lambda field: False)
        assert not merged.root

    def test_get_dependent_fields_yields_the_dependents(self, registry, partner):
        is_company = partner._meta.get_field('is_company')
        dependientes = list(registry.get_dependent_fields(is_company))
        assert partner._meta.get_field('commercial_partner_id') in dependientes

    def test_an_independent_field_yields_nothing(self, registry, partner):
        assert list(registry.get_dependent_fields(partner._meta.get_field('id'))) == []


class TestIsModifyingRelations:
    """``registry.is_modifying_relations`` — si tocar el campo mueve las filas."""

    def test_a_relational_dependency_modifies_relations(self, registry, partner):
        assert registry.is_modifying_relations(partner._meta.get_field('parent')) is True

    def test_a_field_without_dependents_does_not(self, registry, partner):
        """El control: sin disparadores la respuesta es falsa, no verdadera."""
        assert registry.is_modifying_relations(partner._meta.get_field('id')) is False

    def test_the_answer_is_memoised(self, registry, partner):
        parent = partner._meta.get_field('parent')
        registry.is_modifying_relations(parent)
        assert parent in _triggers._modifying


class TestDiscardFields:
    """``registry._discard_fields`` — retira un campo de las cinco estructuras."""

    @pytest.fixture(autouse=True)
    def restore(self):
        """Los mapas derivados son del proceso: se rehacen al salir."""
        yield
        clear_field_depends()

    def test_it_forgets_the_declared_dependencies(self, registry, partner):
        commercial = partner._meta.get_field('commercial_partner_id')
        assert field_depends[commercial]
        registry._discard_fields([commercial])
        assert field_depends[commercial] == ()

    def test_it_empties_the_trigger_memo(self, registry, partner):
        is_company = partner._meta.get_field('is_company')
        registry.get_field_trigger_tree(is_company)
        registry.is_modifying_relations(is_company)
        assert _triggers._trees and _triggers._modifying
        registry._discard_fields([is_company])
        assert _triggers._trees == {}
        assert _triggers._modifying == {}

    def test_it_drops_the_field_from_both_sides_of_the_inverses(self, registry, partner):
        parent = partner._meta.get_field('parent')
        remote = parent.remote_field
        assert registry.field_inverses[parent]
        registry._discard_fields([parent])
        assert registry.field_inverses[parent] == ()
        assert parent not in registry.field_inverses[remote]

    def test_it_drops_the_field_from_the_setup_dependents(self, registry, partner):
        parent = partner._meta.get_field('parent')
        name = partner._meta.get_field('name')
        registry.field_setup_dependents.add(name, parent)
        registry._discard_fields([parent])
        assert parent not in registry.field_setup_dependents[name]

    def test_discarding_an_unknown_field_is_a_no_op(self, registry):
        """El control: la fuente usa ``pop(f, None)`` porque un campo a medida
        puede no estar en los mapas."""
        registry._discard_fields([object()])
