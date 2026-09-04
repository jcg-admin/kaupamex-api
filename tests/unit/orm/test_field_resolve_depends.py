"""``Field.resolve_depends`` — de un nombre punteado a las tuplas de campos.

Ejerce ``odoo19c: odoo/orm/fields.py:807-865`` entero. Es la pieza sobre la
que se apoya el registro de disparadores de la capa B de #273: sin ella el
grafo no tiene aristas, y con ella **a medias** el grafo tiene menos aristas
de las que la declaracion pide, que es peor porque nada lo delata.

El defecto que estos casos cierran: la version anterior emitia **solo la tupla
completa** de cada dependencia. La fuente emite **cada prefijo**, y de ahi sale
que ``owner`` sea por si mismo una clave del grafo. Sin eso,
``is_modifying_relations(owner)`` responde ``False`` sobre un campo que si
cambia que filas dependen de el.

Veredicto por el criterio de las dos categorias:

===========================  ==============================================
El stack lo trae hecho       el registro de campos por nombre
                             (``_meta`` + los descriptores sin columna), la
                             relacion inversa (``remote_field``) y los
                             marcadores de cardinalidad (``one_to_many`` /
                             ``many_to_one``). Los cuatro se leen, no se
                             construyen.
El stack tiene con que       el recorrido en si: Django no resuelve una
construirlo                  cadena punteada a la secuencia de objetos de
                             campo que la componen — resuelve a SQL. La
                             secuencia se compone paso a paso sobre
                             ``related_model``.
===========================  ==============================================
"""
import contextlib
import warnings

import pytest
from django.db import models as django_models

import api
import fields
from orm import registry
from orm.models_transient import TransientModel


class DependsOwner(django_models.Model):
    """El lado uno de la relacion."""

    _name = 'orm.depends.owner'

    label = fields.Char('Label', max_length=32, blank=True)
    child_total = fields.Integer('Child Total',
                                 compute='_compute_child_total', store=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_depends_owner'

    @api.depends('children.source')
    def _compute_child_total(self):
        self.child_total = 0


class DependsChild(django_models.Model):
    """El lado muchos: su ``owner`` es el paso relacional del recorrido."""

    _name = 'orm.depends.child'

    source = fields.Integer('Source', default=0)
    owner = django_models.ForeignKey(
        DependsOwner, on_delete=django_models.CASCADE,
        related_name='children', null=True)
    owner_label = fields.Char('Owner Label', max_length=32,
                              compute='_compute_owner_label', store=True,
                              blank=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_depends_child'

    @api.depends('owner.label')
    def _compute_owner_label(self):
        self.owner_label = ''


class DependsWizard(TransientModel):
    """Un transitorio que depende de un campo de un modelo normal."""

    _name = 'orm.depends.wizard'

    owner = django_models.ForeignKey(
        DependsOwner, on_delete=django_models.CASCADE,
        related_name='wizards', null=True)
    echo = fields.Char('Echo', max_length=32, compute='_compute_echo',
                       store=True, blank=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_depends_wizard'

    @api.depends('owner.label')
    def _compute_echo(self):
        self.echo = ''


def field_of(model, name):
    return model._meta.get_field(name)


def resolved(model, name):
    """Las tuplas que ``model.name`` declara, como tuplas de nombres."""
    field = field_of(model, name)
    return [tuple(step.name for step in path)
            for path in field.resolve_depends(registry)]


@contextlib.contextmanager
def declared_depends(field, dotnames):
    """Declara ``dotnames`` sobre ``field`` mientras dure el bloque.

    Se escribe ``_depends`` —el marcador que ``_DerivedCollector`` lee
    primero— y se vacia el mapa para que se vuelva a derivar. Es la misma via
    por la que ``@api.depends`` llega al registro; no hay un setter publico
    porque el mapa se DERIVA del arbol, y una prueba que lo inyectara por otro
    camino mediria un mapa que el arranque no produce.
    """
    previous = getattr(field, '_depends', None)
    field._depends = tuple(dotnames)
    registry.clear_field_depends()
    try:
        yield
    finally:
        field._depends = previous
        registry.clear_field_depends()


@pytest.fixture(autouse=True)
def fresh_registry():
    registry.clear_field_depends()
    yield
    registry.clear_field_depends()


class TestEveryPrefixIsEmitted:
    """≙ ``yield tuple(field_seq)`` DENTRO del bucle (``:855``)."""

    def test_a_two_step_dependency_emits_both_prefixes(self):
        assert resolved(DependsChild, 'owner_label') == [
            ('owner',), ('owner', 'label')]

    def test_a_one_step_dependency_emits_exactly_one_tuple(self):
        assert resolved(DependsChild, 'owner_label')[0] == ('owner',)

    def test_the_relational_step_is_a_path_of_its_own(self):
        """Es la arista que el grafo necesita para saber que tocar ``owner``
        cambia QUE filas dependen de el, no solo su valor."""
        assert ('owner',) in resolved(DependsChild, 'owner_label')


class TestTheInverseOfAOneToManyIsEmittedToo:
    """≙ ``for inv_field in Model.pool.field_inverses[field]`` (``:858-860``).

    Una dependencia que baja por el lado muchos tambien se dispara cuando
    cambia el ``owner`` de un hijo: el hijo entra o sale del conjunto.
    """

    def test_the_foreign_key_that_inverts_the_relation_is_emitted(self):
        paths = resolved(DependsOwner, 'child_total')
        assert ('children', 'owner') in paths

    def test_the_plain_prefix_is_emitted_before_the_inverse(self):
        paths = resolved(DependsOwner, 'child_total')
        assert paths.index(('children',)) < paths.index(('children', 'owner'))

    def test_the_full_path_is_still_emitted(self):
        assert ('children', 'source') in resolved(DependsOwner, 'child_total')


class TestAFieldDoesNotTriggerItself:
    """≙ ``if not (field is self and not index)`` (``:854``).

    El primer paso de la ruta puede ser el propio campo — un ``one2many`` con
    dominio sobre ``foo`` declara ``line_ids.foo``. Ese prefijo no se emite.
    """

    def test_the_field_itself_as_first_step_is_skipped(self):
        field = field_of(DependsChild, 'owner_label')
        with declared_depends(field, ('owner_label.label',)):
            assert ('owner_label',) not in resolved(DependsChild,
                                                    'owner_label')


class TestAnUnknownNameIsRejected:
    """≙ el ``raise ValueError`` de ``:826-830``, verbatim en su forma.

    La version anterior hacia ``break`` en silencio: una dependencia mal
    escrita desaparecia del grafo sin que nadie lo notara.
    """

    def test_it_names_the_field_and_the_model(self):
        field = field_of(DependsChild, 'owner_label')
        with declared_depends(field, ('no_such_field',)):
            with pytest.raises(ValueError) as excinfo:
                resolved(DependsChild, 'owner_label')
        assert 'no_such_field' in str(excinfo.value)
        assert 'DependsChild' in str(excinfo.value)


class TestARegularModelDoesNotTriggerATransient:
    """≙ el ``break`` de ``:820-824``.

    *"modifying fields on regular models should not trigger recomputations of
    fields on transient models"* — docstring de la fuente, verbatim.
    """

    def test_the_walk_stops_before_leaving_the_transient(self):
        """El corte es al ENTRAR al paso siguiente, no antes del primero: la
        fuente comprueba el modelo actual al inicio de cada vuelta
        (``:821``), asi que ``owner`` —que es un campo del propio
        transitorio— si se emite, y ``owner.label`` no."""
        assert resolved(DependsWizard, 'echo') == [('owner',)]

    def test_the_same_declaration_on_a_regular_model_walks_further(self):
        """El control que discrimina: la MISMA cadena ``owner.label``, sobre
        un modelo normal, si llega al segundo paso. Sin este caso la lista
        corta de arriba no distingue «lo corto el transitorio» de «el
        recorrido nunca pasa del primer paso»."""
        assert resolved(DependsChild, 'owner_label') == [
            ('owner',), ('owner', 'label')]


class TestTheRecursiveWarning:
    """≙ ``:831-833`` — un campo que se alcanza a si mismo lo declara."""

    def test_it_marks_the_field_and_warns(self):
        field = field_of(DependsOwner, 'child_total')
        field.recursive = False
        try:
            with declared_depends(field, ('children.owner.child_total',)):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    list(field.resolve_depends(registry))
            assert field.recursive is True
            assert any('recursive=True' in str(w.message) for w in caught)
        finally:
            field.recursive = False


class TestThePrecomputeWarning:
    """≙ ``:835-838`` — un precomputado no puede depender de uno que no lo es
    salvo que se llegue a el atravesando un ``many2one``."""

    def test_it_clears_precompute_and_warns(self):
        field = field_of(DependsChild, 'owner_label')
        target = field_of(DependsChild, 'source')
        field.precompute = True
        target.compute = '_compute_source'
        try:
            with declared_depends(field, ('source',)):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    list(field.resolve_depends(registry))
            assert field.precompute is False
            assert any('cannot be precomputed' in str(w.message)
                       for w in caught)
        finally:
            field.precompute = False
            target.compute = None

    def test_crossing_a_many_to_one_lifts_the_check(self):
        """El control que discrimina: la MISMA dependencia, alcanzada tras un
        ``many2one``, NO baja ``precompute``. Sin este caso el aviso de arriba
        no distingue «la guarda funciona» de «la guarda dispara siempre»."""
        field = field_of(DependsChild, 'owner_label')
        field.precompute = True
        try:
            with declared_depends(field, ('owner.child_total',)):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    list(field.resolve_depends(registry))
            assert field.precompute is True
            assert not any('cannot be precomputed' in str(w.message)
                           for w in caught)
        finally:
            field.precompute = False
