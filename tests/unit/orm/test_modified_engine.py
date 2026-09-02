"""Capa C de #273 — ``modified()``: quien recorre el grafo y marca el recalculo.

Ejerce ``odoo19c: odoo/orm/models.py:6756-6959``: ``modified``, ``_modified``,
``_modified_triggers``, ``_recompute_model``, ``_recompute_recordset`` y
``_recompute_field``.

Cierra el motor. Las tres capas, en una linea cada una:

- **A** — el campo sabe recalcularse y cachear su valor.
- **B** — el grafo sabe QUE campos dependen de cual, y por que camino.
- **C** — alguien recorre ese grafo cuando un valor cambia, y marca.

Sin la C el grafo esta construido y nadie lo recorre; sin la A hay a quien
marcar y nada que ejecutar. Los tres se necesitan.

Veredicto por el criterio de las dos categorias:

===========================  ==============================================
El stack lo trae hecho       la navegacion inversa (``related manager``), la
                             busqueda por ``__in`` y el marcador de fila sin
                             persistir (``pk is None``). Ninguno se
                             construye: se leen.
El stack tiene con que       el marcado en si. Django no tiene la nocion de
construirlo                  «campo pendiente de recalculo»: la
                             ``Transaction`` de ``orm/environments`` la
                             aporta con ``tocompute``, y sobre eso el
                             recorrido es un ``chain`` perezoso sobre el
                             arbol que la capa B construye.
===========================  ==============================================
"""
import pytest
from django.db import connection
from django.db import models as django_models

import api
import fields
from orm import registry
from orm.environments import env, transaction_scope


class EngineOwner(django_models.Model):
    """El lado uno: su etiqueta es la dependencia lejana."""

    _name = 'orm.engine.owner'

    label = fields.Char('Label', max_length=32, blank=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_engine_owner'


class EngineProbe(django_models.Model):
    """El lado muchos: un calculado local y otro a traves de la relacion."""

    _name = 'orm.engine.probe'

    source = fields.Integer('Source', default=0)
    owner = django_models.ForeignKey(
        EngineOwner, on_delete=django_models.CASCADE,
        related_name='probes', null=True)
    doubled = fields.Integer('Doubled', compute='_compute_doubled',
                             store=True, null=True)
    owner_label = fields.Char('Owner Label', max_length=32,
                              compute='_compute_owner_label', store=True,
                              blank=True, null=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_engine_probe'

    @api.depends('source')
    def _compute_doubled(self):
        self.doubled = (self.source or 0) * 2

    @api.depends('owner.label')
    def _compute_owner_label(self):
        self.owner_label = self.owner.label if self.owner_id else ''


def field_of(model, name):
    return model._meta.get_field(name)


@pytest.fixture(scope='session')
def tables(django_db_setup, django_db_blocker):
    """Crea las dos tablas de prueba una vez por sesion.

    Los dos modelos son sondas de este archivo y no tienen migracion, asi que
    la tabla se crea con el ``schema_editor``. La creacion va **fuera** de la
    transaccion de cada caso —de ahi el ambito de sesion y el
    ``django_db_blocker``—: dentro, el ``rollback`` de pytest-django se
    llevaria el DDL por delante.
    """
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in (EngineOwner, EngineProbe):
                editor.create_model(model)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in (EngineProbe, EngineOwner):
                editor.delete_model(model)


@pytest.fixture(autouse=True)
def fresh_registry():
    registry.clear_field_depends()
    yield
    registry.clear_field_depends()


@pytest.fixture
def probe():
    """Una fila sin persistir: el motor no exige base para marcar."""
    return EngineProbe(pk=1, source=3)


@pytest.fixture
def owner():
    return EngineOwner(pk=10, label='uno')


class TestTheLocalDependencyMarks:
    """Un campo calculado se marca cuando cambia aquel del que depende."""

    def test_touching_the_source_marks_the_computed_field(self, probe):
        with transaction_scope():
            probe.modified(['source'])
            pending = env().records_to_compute(field_of(EngineProbe, 'doubled'))
            assert probe.pk in pending

    def test_an_unrelated_field_marks_nothing(self, probe):
        """El control que discrimina: la MISMA maquinaria sobre un campo del
        que nadie depende no marca a nadie. Sin este caso, el de arriba no
        distingue «el grafo funciona» de «se marca todo siempre»."""
        with transaction_scope():
            probe.modified(['doubled'])
            assert not env().records_to_compute(
                field_of(EngineProbe, 'doubled'))

    def test_no_field_names_is_a_no_op(self, probe):
        with transaction_scope():
            probe.modified([])
            assert not env().fields_to_compute()


class TestTheFarDependencyWalksBackwards:
    """≙ el recorrido inverso de ``_modified_triggers`` (``:6881-6916``)."""

    def test_touching_the_owner_marks_the_probe(self, db, tables):
        owner = EngineOwner.objects.create(label='uno')
        probe = EngineProbe.objects.create(source=1, owner=owner)
        with transaction_scope():
            owner.modified(['label'])
            pending = env().records_to_compute(
                field_of(EngineProbe, 'owner_label'))
            assert probe.pk in pending

    def test_an_owner_without_probes_marks_nothing(self, db, tables):
        """El control que discrimina: el mismo campo, sin nadie que apunte,
        no marca. La vuelta se hace de verdad, no se supone."""
        lonely = EngineOwner.objects.create(label='solo')
        with transaction_scope():
            lonely.modified(['label'])
            assert not env().records_to_compute(
                field_of(EngineProbe, 'owner_label'))

    def test_only_the_probes_of_that_owner_are_marked(self, db, tables):
        first = EngineOwner.objects.create(label='uno')
        second = EngineOwner.objects.create(label='dos')
        mine = EngineProbe.objects.create(source=1, owner=first)
        other = EngineProbe.objects.create(source=2, owner=second)
        with transaction_scope():
            first.modified(['label'])
            pending = env().records_to_compute(
                field_of(EngineProbe, 'owner_label'))
            assert mine.pk in pending
            assert other.pk not in pending


class TestCreateSkipsTheManyToOneReturn:
    """≙ ``:6884-6886`` — al crear, ninguna otra fila referencia aun a self."""

    def test_on_create_the_backward_walk_is_skipped(self, db, tables):
        owner = EngineOwner.objects.create(label='uno')
        EngineProbe.objects.create(source=1, owner=owner)
        with transaction_scope():
            owner.modified(['label'], create=True)
            assert not env().records_to_compute(
                field_of(EngineProbe, 'owner_label'))

    def test_without_create_the_same_call_does_mark(self, db, tables):
        """El control positivo del anterior: es el flag quien corta, no la
        ausencia de filas que marcar."""
        owner = EngineOwner.objects.create(label='uno')
        probe = EngineProbe.objects.create(source=1, owner=owner)
        with transaction_scope():
            owner.modified(['label'], create=False)
            assert probe.pk in env().records_to_compute(
                field_of(EngineProbe, 'owner_label'))


class TestTheProtectedAreNotMarked:
    """≙ ``records -= self.env.protected(field)`` (``:6806``)."""

    def test_a_protected_row_is_left_alone(self, probe):
        doubled = field_of(EngineProbe, 'doubled')
        with transaction_scope():
            with env().protecting([doubled], [probe.pk]):
                probe.modified(['source'])
            assert probe.pk not in env().records_to_compute(doubled)

    def test_outside_the_protection_the_same_call_marks(self, probe):
        doubled = field_of(EngineProbe, 'doubled')
        with transaction_scope():
            probe.modified(['source'])
            assert probe.pk in env().records_to_compute(doubled)


class TestBeforeDefersTheMark:
    """≙ el bloque ``before`` (``:6788-6798`` y ``:6833-6837``).

    Llamado ANTES de modificar, lo que depende de self no debe recalcularse
    todavia: se acumula y se marca al final, no durante el recorrido.
    """

    def test_the_mark_lands_after_the_walk_finishes(self, probe):
        doubled = field_of(EngineProbe, 'doubled')
        with transaction_scope():
            probe.modified(['source'], before=True)
            assert probe.pk in env().records_to_compute(doubled)


class TestRecompute:
    """Los tres ``_recompute_*`` y su reparto de alcance."""

    def test_the_recordset_variant_computes_only_its_rows(self, db, tables):
        first = EngineProbe.objects.create(source=3)
        second = EngineProbe.objects.create(source=5)
        doubled = field_of(EngineProbe, 'doubled')
        with transaction_scope():
            env().add_to_compute(doubled, [first.pk, second.pk])
            first._recompute_recordset(['doubled'])
            pending = env().records_to_compute(doubled)
            assert first.pk not in pending
            assert second.pk in pending

    def test_the_model_variant_computes_every_pending_row(self, db, tables):
        first = EngineProbe.objects.create(source=3)
        second = EngineProbe.objects.create(source=5)
        doubled = field_of(EngineProbe, 'doubled')
        with transaction_scope():
            env().add_to_compute(doubled, [first.pk, second.pk])
            first._recompute_model(['doubled'])
            assert not env().records_to_compute(doubled)

    def test_a_field_with_nothing_pending_is_a_no_op(self, db, tables):
        row = EngineProbe.objects.create(source=3)
        doubled = field_of(EngineProbe, 'doubled')
        with transaction_scope():
            row._recompute_field(doubled)
            assert not env().records_to_compute(doubled)


class TestTheEngineClosesTheCircle:
    """De punta a punta: cambiar el origen deja el calculado con su valor."""

    def test_the_marked_field_reaches_the_column_on_flush(self, db, tables):
        """De punta a punta y hasta la COLUMNA: marcar, recalcular y volcar.

        El ``refresh_from_db`` es el control que discrimina: sin el, el valor
        vive en el atributo de la instancia y la fila de la base sigue con el
        viejo — que es la mitad silenciosa que ``store=True`` promete.
        """
        row = EngineProbe.objects.create(source=7)
        with transaction_scope():
            row.modified(['source'])
            row.flush_recordset(['doubled'])
        row.refresh_from_db()
        assert row.doubled == 14

    def test_without_the_flush_the_column_keeps_the_old_value(self, db, tables):
        """El control positivo del anterior: el recalculo solo NO escribe. Es
        el reparto de la fuente —``_recompute_*`` calcula, ``_flush``
        escribe— y aqui queda medido en vez de supuesto."""
        row = EngineProbe.objects.create(source=7)
        with transaction_scope():
            row.modified(['source'])
            row._recompute_recordset(['doubled'])
        fresh = EngineProbe.objects.get(pk=row.pk)
        assert fresh.doubled is None
