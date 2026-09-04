"""Capa B de #273 — el registro de disparadores: quién depende de quién.

Ejerce lo que ``odoo19c: odoo/orm/registry.py:506-690`` declara:
``field_inverses``, ``_field_triggers``, ``get_field_trigger_tree``,
``get_trigger_tree``, ``get_dependent_fields`` e ``is_modifying_relations``;
más ``Collector`` (``odoo19c: odoo/tools/misc.py:988``).

Es la **inversa** de la capa A. Aquélla sabe recalcular un campo; ésta sabe
QUÉ campos hay que recalcular cuando uno cambia, y por qué camino llegar a las
filas afectadas.

Veredicto por el criterio de las dos categorías:

===========================  ==============================================
El stack lo trae hecho       la relación inversa. Django la mantiene en
                             ``remote_field`` y la publica en
                             ``_meta.get_fields()``; la fuente tiene que
                             construirla con un ``setup_inverses`` por clase
                             porque su ORM no la guarda.
El stack tiene con qué       el grafo de disparo. Django no invierte una
construirlo                  dependencia declarada —no tiene el concepto—,
                             pero ``resolve_depends`` ya resuelve el nombre
                             punteado a su tupla de campos, y sobre eso el
                             cierre transitivo es un recorrido.
===========================  ==============================================
"""
import pytest
from django.db import models as django_models

import api
import fields
from orm import registry
from tools.misc import Collector


class TriggerOwner(django_models.Model):
    """El lado uno: su nombre es la dependencia lejana."""

    _name = 'orm.trigger.owner'

    label = fields.Char('Label', max_length=32, blank=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_trigger_owner'


class TriggerProbe(django_models.Model):
    """El lado muchos: dos calculados, uno local y uno a través de la relación."""

    _name = 'orm.trigger.probe'

    source = fields.Integer('Source', default=0)
    owner = django_models.ForeignKey(
        TriggerOwner, on_delete=django_models.CASCADE,
        related_name='probes', null=True)
    doubled = fields.Integer('Doubled', compute='_compute_doubled', store=True)
    owner_label = fields.Char('Owner Label', max_length=32,
                              compute='_compute_owner_label', store=True,
                              blank=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_trigger_probe'

    @api.depends('source')
    def _compute_doubled(self):
        self.doubled = (self.source or 0) * 2

    @api.depends('owner.label')
    def _compute_owner_label(self):
        self.owner_label = self.owner.label if self.owner_id else ''


def field_of(model, name):
    return model._meta.get_field(name)


@pytest.fixture(autouse=True)
def fresh_registry():
    """El registro se deriva del árbol; cada caso parte de un mapa limpio."""
    registry.clear_field_depends()
    yield
    registry.clear_field_depends()


class TestTheCollectorIsARelation:
    """``Collector`` — un mapa de clave a tupla, sin crear lo ausente."""

    def test_an_absent_key_gives_the_empty_tuple(self):
        assert Collector()['nadie'] == ()

    def test_reading_an_absent_key_does_not_create_it(self):
        collector = Collector()
        collector['nadie']
        assert len(collector) == 0

    def test_add_accumulates_without_repeating(self):
        collector = Collector()
        collector.add('a', 1)
        collector.add('a', 2)
        collector.add('a', 1)
        assert collector['a'] == (1, 2)

    def test_assigning_an_empty_value_removes_the_key(self):
        collector = Collector()
        collector.add('a', 1)
        collector['a'] = ()
        assert 'a' not in collector

    def test_discard_removes_the_key_and_the_value(self):
        collector = Collector()
        collector.add('a', 1)
        collector.add('b', 1)
        collector.add('b', 2)
        collector.discard_keys_and_values(['a', 1])
        assert 'a' not in collector
        assert collector['b'] == (2,)


class TestTheInverseComesFromTheStack:
    """La relación inversa la mantiene Django; no hace falta construirla."""

    def test_a_foreign_key_knows_its_reverse(self):
        inverses = registry.field_inverses
        owner = field_of(TriggerProbe, 'owner')
        assert field_of(TriggerOwner, 'probes') in inverses[owner]

    def test_the_reverse_knows_the_foreign_key(self):
        inverses = registry.field_inverses
        reverse = field_of(TriggerOwner, 'probes')
        assert field_of(TriggerProbe, 'owner') in inverses[reverse]

    def test_a_plain_field_has_no_inverse(self):
        assert registry.field_inverses[field_of(TriggerProbe, 'source')] == ()


class TestTheTriggersInvertTheDependency:

    def test_a_local_dependency_lands_at_the_empty_path(self):
        triggers = registry.field_triggers()
        source = field_of(TriggerProbe, 'source')
        assert field_of(TriggerProbe, 'doubled') in triggers[source][()]

    def test_a_dotted_dependency_carries_the_field_to_inverse(self):
        triggers = registry.field_triggers()
        label = field_of(TriggerOwner, 'label')
        paths = triggers[label]
        assert (field_of(TriggerProbe, 'owner'),) in paths
        assert field_of(TriggerProbe, 'owner_label') in paths[
            (field_of(TriggerProbe, 'owner'),)]

    def test_a_field_nobody_depends_on_is_absent(self):
        assert field_of(TriggerProbe, 'doubled') not in registry.field_triggers()


class TestTheTreeAndItsReaders:

    def test_the_tree_of_a_local_dependency_has_it_at_the_root(self):
        tree = registry.get_field_trigger_tree(field_of(TriggerProbe, 'source'))
        assert field_of(TriggerProbe, 'doubled') in tree.root

    def test_the_tree_of_a_far_dependency_hangs_from_the_field_to_inverse(self):
        tree = registry.get_field_trigger_tree(field_of(TriggerOwner, 'label'))
        branch = tree[field_of(TriggerProbe, 'owner')]
        assert field_of(TriggerProbe, 'owner_label') in branch.root

    def test_a_field_without_triggers_gives_an_empty_tree(self):
        tree = registry.get_field_trigger_tree(field_of(TriggerProbe, 'doubled'))
        assert not tree

    def test_the_dependent_fields_are_listed(self):
        dependents = list(
            registry.get_dependent_fields(field_of(TriggerProbe, 'source')))
        assert field_of(TriggerProbe, 'doubled') in dependents

    def test_a_field_without_triggers_lists_nothing(self):
        assert list(registry.get_dependent_fields(
            field_of(TriggerProbe, 'doubled'))) == []

    def test_the_merged_tree_covers_every_given_field(self):
        tree = registry.get_trigger_tree([
            field_of(TriggerProbe, 'source'), field_of(TriggerOwner, 'label')])
        assert field_of(TriggerProbe, 'doubled') in tree.root
        assert field_of(TriggerProbe, 'owner_label') in tree[
            field_of(TriggerProbe, 'owner')].root

    def test_select_discards_what_it_rejects(self):
        tree = registry.get_trigger_tree(
            [field_of(TriggerProbe, 'source')], select=lambda field: False)
        assert not tree


class TestModifyingRelations:
    """Si tocar el campo puede cambiar QUÉ filas dependen de él."""

    def test_a_relational_field_with_dependents_modifies_relations(self):
        assert registry.is_modifying_relations(field_of(TriggerProbe, 'owner'))

    def test_a_field_without_dependents_does_not(self):
        assert not registry.is_modifying_relations(
            field_of(TriggerProbe, 'doubled'))


class TestTheCachesFollowTheDeclaration:
    """El control: si el mapa derivado no se vacía, sirve el árbol viejo."""

    def test_clearing_rebuilds_the_trigger_map(self):
        primero = registry.field_triggers()
        registry.clear_field_depends()
        assert registry.field_triggers() is not primero

    def test_clearing_rebuilds_the_tree_cache(self):
        source = field_of(TriggerProbe, 'source')
        primero = registry.get_field_trigger_tree(source)
        assert registry.get_field_trigger_tree(source) is primero
        registry.clear_field_depends()
        assert registry.get_field_trigger_tree(source) is not primero
