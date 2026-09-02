"""La familia ``related=`` de ``Field`` — ≙ ``odoo19c: :557-772``.

``related='partner_id.country_id.name'`` declara un campo cuyo valor no vive en
su propia fila: se lee recorriendo la cadena punteada hasta el campo del
extremo. La fuente lo resuelve dándole al campo un ``compute`` y un ``inverse``
propios, que son estos métodos.

Dos cosas que la fuente marca como contrato y que aquí se comprueban:

- el **orden** del recorrido de ``_compute_related`` —todos los registros en un
  campo antes de pasar al siguiente— porque es lo que deja funcionar la
  prelectura;
- la lectura **antes** de escribir en ``_inverse_related``, porque escribir en
  el extremo invalida la caché del origen.
"""
import pytest
from django.db import models

from orm import registry


class _Recorder:
    """Un registro de mentira que anota en qué orden le piden cada campo.

    Hace falta porque el orden del recorrido no deja rastro en el resultado:
    las dos formas dan el mismo valor. Sin este espía, el caso del orden sería
    un verde que no discrimina.
    """

    def __init__(self, name, chain, log):
        self.name = name
        self.chain = chain
        self.log = log
        self.written = {}
        self.id = 1

    def __getitem__(self, key):
        self.log.append((self.name, key))
        return self.chain[key]

    def __setitem__(self, key, value):
        self.written[key] = value

    def __iter__(self):
        return iter(())


class TestTheTraversalOrder:

    def test_it_walks_field_by_field_not_record_by_record(self):
        """El control que discrimina: la fuente dedica veinte líneas de
        comentario a este orden y lo llama *«a major impact on performance»*.
        Recorrer registro a registro pide el campo del extremo de uno en uno;
        recorrer campo a campo lo pide para todo el lote."""
        log = []
        leaf = models.CharField(max_length=8)
        leaf.set_attributes_from_name('name')

        def make(label):
            deep = _Recorder(f'{label}.deep', {'name': f'valor-{label}'}, log)
            return _Recorder(label, {'middle': deep}, log)

        records = [make('a1'), make('a2')]
        field = models.CharField(max_length=8)
        field.set_attributes_from_name('shortcut')
        field.related = 'middle.name'
        field.related_field = leaf

        field._compute_related(records)

        assert log == [('a1', 'middle'), ('a2', 'middle'),
                       ('a1.deep', 'name'), ('a2.deep', 'name')]
        assert records[0].written['shortcut'] == 'valor-a1'
        assert records[1].written['shortcut'] == 'valor-a2'


class TestTraverseRelated:

    def test_it_stops_before_the_last_field(self):
        leaf = models.CharField(max_length=8)
        leaf.set_attributes_from_name('name')
        deep = _Recorder('deep', {}, [])
        record = _Recorder('root', {'middle': deep}, [])

        field = models.CharField(max_length=8)
        field.related = 'middle.name'
        field.related_field = leaf

        target, last = field.traverse_related(record)
        assert target is deep
        assert last is leaf

    def test_an_empty_container_is_kept_not_dropped(self):
        """Verbatim de la fuente: ``next(iter(corecord), corecord)`` conserva
        el contenedor vacío para que el llamador distinga «no hay» de «no se
        recorrió»."""
        empty = _Recorder('vacio', {}, [])
        record = _Recorder('root', {'middle': empty}, [])
        field = models.CharField(max_length=8)
        field.related = 'middle.name'
        field.related_field = models.CharField(max_length=8)
        target, _ = field.traverse_related(record)
        assert target is empty


class TestInverseRelated:

    def test_it_reads_every_value_before_writing_any(self):
        """La fuente lo dice en su comentario: *«store record values,
        otherwise they may be lost by cache invalidation»*. Escribir en el
        extremo invalida la caché del origen."""
        leaf = models.CharField(max_length=8)
        leaf.set_attributes_from_name('name')
        target = _Recorder('target', {}, [])
        record = _Recorder('root', {'shortcut': 'valor', 'middle': target}, [])

        field = models.CharField(max_length=8)
        field.set_attributes_from_name('shortcut')
        field.related = 'middle.name'
        field.related_field = leaf

        field._inverse_related([record])
        assert target.written['name'] == 'valor'

    def test_it_does_not_cross_the_saved_boundary(self):
        """Verbatim: sólo se propaga entre dos registros ambos reales o ambos
        nuevos. Un registro sin guardar no escribe en uno guardado."""
        leaf = models.CharField(max_length=8)
        leaf.set_attributes_from_name('name')
        target = _Recorder('target', {}, [])
        target.id = 7
        record = _Recorder('root', {'shortcut': 'valor', 'middle': target}, [])
        record.id = None

        field = models.CharField(max_length=8)
        field.set_attributes_from_name('shortcut')
        field.related = 'middle.name'
        field.related_field = leaf

        field._inverse_related([record])
        assert 'name' not in target.written


class TestTheSmallOnes:

    def test_prepare_setup_reopens_the_setup(self):
        field = models.CharField(max_length=8)
        assert field._setup_done is True
        field.prepare_setup()
        assert field._setup_done is False

    def test_setup_nonrelated_is_the_empty_hook(self):
        """Se porta con su cuerpo vacío porque el símbolo ES el contrato:
        quitarlo obligaría a cada subclase a saber si su base lo declara."""
        assert models.CharField(max_length=8).setup_nonrelated(None) is None

    def test_process_related_does_not_transform(self):
        field = models.CharField(max_length=8)
        sentinel = object()
        assert field._process_related(sentinel, None) is sentinel


class TestResolveDepends:

    def test_a_field_without_declarations_yields_nothing(self):
        field = models.CharField(max_length=8)
        field.model_name = 'res.partner'
        assert list(field.resolve_depends(registry)) == []

    def test_an_unknown_model_yields_nothing_instead_of_raising(self):
        field = models.CharField(max_length=8)
        field.model_name = 'modelo.que.no.existe'
        assert list(field.resolve_depends(registry)) == []

    def test_it_finds_the_model_the_django_way(self, db):
        """Control que discrimina las dos vías: un campo ligado por Django
        lleva ``field.model`` y NO ``model_name``. Resolviendo sólo por el
        segundo —como la fuente— quedarían fuera todos."""
        field = registry.MODELS_BY_NAME['res.partner']._meta.get_field('name')
        assert field.model is not None
        assert not field.model_name

    @staticmethod
    def _resolved_with(field, dotnames):
        """Resuelve ``dotnames`` sobre ``field`` con el mapa sustituido."""
        collector = registry._DerivedCollector('_depends')
        collector._table = {field: dotnames}
        original = registry.field_depends
        registry.field_depends = collector
        try:
            return list(field.resolve_depends(registry))
        finally:
            registry.field_depends = original

    def test_it_resolves_a_declared_chain_to_its_fields(self, db):
        """El control de punta a punta: una dependencia declarada como nombre
        punteado sale como la tupla de campos que la recorre — y sale **cada
        prefijo**, no solo la tupla entera (``odoo19c: :855``).

        > **Actualizado en cadena (tarea #273, capa B).** Este caso declaraba
        > ``{name: ('name',)}`` y esperaba ``[(name,)]``. Las dos mitades eran
        > consecuencia del porte incompleto: la fuente **no** emite el primer
        > paso cuando es el propio campo (``:854``), asi que esa declaracion
        > resuelve a la lista vacia y nunca fue un control de «resuelve la
        > cadena». Se cambia a una cadena real de dos pasos, que es lo que el
        > nombre del caso dice medir; el contrato del primer paso se mide
        > aparte, abajo.
        """
        partner = registry.MODELS_BY_NAME['res.partner']
        field = partner._meta.get_field('name')
        parent = partner._meta.get_field('parent')
        parent_name = parent.related_model._meta.get_field('name')
        assert self._resolved_with(field, ('parent.name',)) == [
            (parent,), (parent, parent_name)]

    def test_a_field_does_not_trigger_itself_as_the_first_step(self, db):
        """≙ ``if not (field is self and not index)`` (``:854``).

        Es el control que discrimina al de arriba: la MISMA maquinaria, con el
        campo como primer paso de su propia dependencia, no emite nada.
        """
        partner = registry.MODELS_BY_NAME['res.partner']
        field = partner._meta.get_field('name')
        assert self._resolved_with(field, ('name',)) == []
