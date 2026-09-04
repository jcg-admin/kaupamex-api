"""#331 — los cuatro del ciclo de vida que portan contra lo que ya existe.

De los ocho símbolos de nivel 3 que el censo deja sin contraparte en el ciclo
de vida de la clase de modelo, éstos cuatro no necesitan construir nada antes:

======================= ================================ =========================
Símbolo                 En la referencia                  Aquí
======================= ================================ =========================
``to_record_ids``       ``models.py:159-166``            ``orm/models.py``
``add_field``           ``model_classes.py:596-619``     ``orm/model_classes.py``
``pop_field``           ``model_classes.py:622-633``     ``orm/model_classes.py``
``_check_inherits``     ``model_classes.py:465-477``     ``orm/model_classes.py``
======================= ================================ =========================

Los otros cuatro —``_init_model_class_attributes``, ``_prepare_setup`` y los
dos ``_check_model_*_extension``— exigen construir antes los tres colectores
de método marcado, ``_transient`` y ``_inherits_children``, ninguno presente.
Es la tarea **#332**. El quinto prerrequisito que aquella listaba,
``discardattr``, se porta aquí porque ``pop_field`` lo consume.

Los controles que discriminan
==============================

- ``to_record_ids`` **descarta el id falso**: una fila sin guardar no aporta
  id. Sin el filtro, la lista traería ``None`` y el caso pasaría igual.
- ``add_field`` tiene **dos** validaciones; cada una tiene su caso negativo, y
  el positivo mide que el campo queda consultable por ``_meta``.
- ``pop_field`` arregla ``_rec_name`` **y** caduca las dependencias
  derivadas: la segunda mitad es la que un ``delattr`` pelado no hace.
- ``_check_inherits`` mide **cuatro** propiedades del campo delegado —tipo,
  delegación, obligatoriedad y política de borrado— y hay un caso por cada
  una, más el control positivo sobre los declarantes vivos del árbol.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import models

from orm import registry
from orm.identifiers import NewId
from orm.model_classes import _check_inherits, add_field, pop_field
from orm.models import to_record_ids


class TestToRecordIdsNormalizesTheThreeShapes:
    """≙ ``to_record_ids`` (``odoo19c: odoo/orm/models.py:159-166``) — «Return
    the record ids of ``arg``, which may be a recordset, an integer or a list
    of integers»."""

    def test_an_integer_comes_back_wrapped(self):
        assert to_record_ids(7) == [7]

    def test_the_falsy_integer_gives_the_empty_list(self):
        assert to_record_ids(0) == []

    def test_a_list_comes_through_filtered(self):
        assert to_record_ids([1, 0, 2, None]) == [1, 2]

    def test_an_empty_iterable_gives_the_empty_list(self):
        assert to_record_ids([]) == []

    @pytest.mark.django_db
    def test_a_saved_row_gives_its_id(self):
        row = registry.MODELS_BY_NAME['res.partner'](pk=41)
        assert to_record_ids(row) == [41]

    @pytest.mark.django_db
    def test_an_unsaved_row_gives_nothing(self):
        """EL CONTROL: la fuente resuelve el recordset con ``OriginIds``
        (``models.py:5905-5909``), que descarta el id falso. Sin ese filtro la
        lista traería ``None`` y el caso pasaría igual de verde."""
        assert to_record_ids(registry.MODELS_BY_NAME['res.partner']()) == []

    def test_a_bare_list_of_new_ids_comes_back_empty(self):
        """La asimetría de la fuente, conservada: la rama del iterable filtra
        por verdad y un ``NewId`` es falso, así que **no** se resuelve a su
        origen. Sólo la rama de la fila pasa por ``OriginIds``."""
        assert to_record_ids([NewId(origin=7)]) == []


@pytest.mark.django_db
class TestAddFieldHangsTheFieldOnTheBuiltClass:
    """≙ ``add_field`` (``model_classes.py:596-619``)."""

    def test_it_hangs_a_manual_field_and_meta_finds_it(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        add_field(partner, 'x_probe_alta',
                  models.CharField(max_length=8, null=True))
        try:
            assert partner._meta.get_field('x_probe_alta') is not None
        finally:
            pop_field(partner, 'x_probe_alta')

    def test_it_marks_the_field_as_top_level(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        add_field(partner, 'x_probe_toplevel',
                  models.CharField(max_length=8, null=True))
        try:
            assert partner._meta.get_field('x_probe_toplevel')._toplevel is True
        finally:
            pop_field(partner, 'x_probe_toplevel')

    def test_a_name_neither_declared_nor_manual_is_refused(self):
        """EL CONTROL de la primera validación: la fuente sólo admite el
        nombre que la clase Python ya declara o el que empieza por ``x_``."""
        partner = registry.MODELS_BY_NAME['res.partner']
        with pytest.raises(ValidationError, match='not defined'):
            add_field(partner, 'inventado', models.CharField(max_length=8))

    def test_something_that_is_not_a_field_is_refused(self):
        """EL CONTROL de la segunda: *"You can only add ``fields.Field``
        objects to a model fields"*."""
        partner = registry.MODELS_BY_NAME['res.partner']
        with pytest.raises(ValidationError, match='only add'):
            add_field(partner, 'x_probe_no_campo', 'no soy un campo')

    def test_a_declared_name_passes_the_first_validation(self):
        """Un nombre que la clase declara entra sin ser ``x_``: es la otra
        rama de la primera validación."""
        partner = registry.MODELS_BY_NAME['res.partner']
        original = partner._meta.get_field('comment')
        add_field(partner, 'comment', models.TextField(null=True, blank=True))
        try:
            assert partner._meta.get_field('comment') is not original
        finally:
            # El restablecimiento NO puede pasar por ``add_field``: tras
            # ``pop_field`` el nombre ya no lo declara la clase, asi que su
            # primera validacion lo rechazaria — y eso es fiel a la fuente,
            # cuyo ``getattr(model, name, None)`` tampoco lo encontraria. Se
            # devuelve con el mecanismo de Django, sin validar.
            pop_field(partner, 'comment')
            partner.add_to_class('comment', original)


@pytest.mark.django_db
class TestPopFieldTakesTheFieldOffAgain:
    """≙ ``pop_field`` (``model_classes.py:622-633``)."""

    def test_it_returns_the_field_it_removed(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        field = models.CharField(max_length=8, null=True)
        add_field(partner, 'x_probe_baja', field)
        assert pop_field(partner, 'x_probe_baja') is field

    def test_meta_stops_finding_it(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        add_field(partner, 'x_probe_meta',
                  models.CharField(max_length=8, null=True))
        pop_field(partner, 'x_probe_meta')
        with pytest.raises(Exception):
            partner._meta.get_field('x_probe_meta')

    def test_an_absent_name_gives_none(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        assert pop_field(partner, 'x_probe_que_no_esta') is None

    def test_it_clears_rec_name_when_it_was_the_one(self):
        """EL CONTROL de la segunda mitad: un ``delattr`` pelado dejaría
        ``_rec_name`` apuntando a un campo que ya no existe."""
        partner = registry.MODELS_BY_NAME['res.partner']
        add_field(partner, 'x_probe_rec',
                  models.CharField(max_length=8, null=True))
        previous = partner.__dict__.get('_rec_name')
        partner._rec_name = 'x_probe_rec'
        try:
            pop_field(partner, 'x_probe_rec')
            assert partner._rec_name is None
        finally:
            if previous is None:
                partner.__dict__.pop('_rec_name', None)
            else:
                partner._rec_name = previous


@pytest.mark.django_db
class TestCheckInheritsValidatesTheDelegatedField:
    """≙ ``_check_inherits`` (``model_classes.py:465-477``).

    La firma es la de la fuente —recibe la clase y lee su ``_inherits``—, así
    que los casos negativos se montan sustituyendo esa declaración en un
    modelo real y restaurándola. No hay doble: el mecanismo que se mide es el
    que corre en producción.
    """

    def test_the_live_declarants_pass(self):
        """EL CONTROL POSITIVO, y no es un doble: los modelos del árbol que
        declaran ``_inherits`` tienen que pasar su propia validación.

        **La lista se DERIVA, no se enumera.** Enumerarla convertía cada
        declarante nuevo en un rojo que no dice nada del mecanismo: el
        asistente de banco de #333 lo rompió sin tocar ``_check_inherits``.
        Lo que el caso mide es que TODOS pasan, y que hay alguno que medir —
        sin ese piso el bucle sobre una lista vacía sería verde por vacío,
        que es el sub-patrón D de ``metrica-decide-la-conclusion.md``.
        """
        declarants = [model for model in registry.MODELS_BY_NAME.values()
                      if model.__dict__.get('_inherits')]
        assert declarants, 'ningún modelo del árbol declara _inherits'
        for model in declarants:
            _check_inherits(model)

    def test_a_missing_field_is_refused(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        partner._inherits = {'res.company': 'no_existe'}
        try:
            with pytest.raises(TypeError, match='Missing many2one'):
                _check_inherits(partner)
        finally:
            del partner._inherits

    def test_a_field_that_is_not_a_foreign_key_is_refused(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        partner._inherits = {'res.company': 'comment'}
        try:
            with pytest.raises(TypeError, match='Missing many2one'):
                _check_inherits(partner)
        finally:
            del partner._inherits

    def test_a_field_that_does_not_delegate_is_refused(self):
        users = registry.MODELS_BY_NAME['res.users']
        field = users._meta.get_field('partner')
        field.delegate = False
        try:
            with pytest.raises(TypeError, match='delegate'):
                _check_inherits(users)
        finally:
            field.delegate = True

    def test_a_nullable_field_is_refused(self):
        """La fuente exige ``required``; aquí eso es ``null=False``."""
        users = registry.MODELS_BY_NAME['res.users']
        field = users._meta.get_field('partner')
        field.null = True
        try:
            with pytest.raises(TypeError, match='delegate'):
                _check_inherits(users)
        finally:
            field.null = False

    def test_a_wrong_ondelete_policy_is_refused(self):
        """EL CONTROL de la cuarta propiedad: la fuente sólo admite
        ``cascade`` o ``restrict``; aquí, ``CASCADE`` o ``PROTECT``."""
        users = registry.MODELS_BY_NAME['res.users']
        remote = users._meta.get_field('partner').remote_field
        previous = remote.on_delete
        remote.on_delete = models.SET_NULL
        try:
            with pytest.raises(TypeError, match='delegate'):
                _check_inherits(users)
        finally:
            remote.on_delete = previous
