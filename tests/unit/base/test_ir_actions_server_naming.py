"""El nombre automático y la superficie derivada de ``ir.actions.server`` (#117).

≙ ``odoo19c: addons/base/models/ir_actions.py:605-606`` (``name`` y
``automated_name``), ``:819-848`` (``_generate_action_name``, ``_name_depends``,
``_compute_name``, ``_onchange_name``), ``:630`` y ``:799-800``
(``allowed_states``), ``:637`` y ``:851-856`` (``available_model_ids``),
``:694-701`` y ``:1244-1257`` (``value_field_to_show``), ``:657`` y ``:667``
(los dos ``related``), ``:811-817`` (``_get_children_domain``), ``:840-845``
(``_check_python_code``), ``:1259-1261`` (``_selection_target_model``),
``:1263-1283`` (los tres ``_set_*``) y ``:1320-1326`` (``copy_data``).

Qué haría fallar a estos casos
==============================

El nombre automático tiene **dos** estados que un caso ingenuo confunde: el
que el usuario escribió y el que la acción generó. Un caso que sólo mirase
``name`` tras cambiar ``state`` pasaría con ``automated_name`` ausente — por
eso cada caso afirma **cuál de los dos** cambió.

``_get_children_domain`` se mide por el ``repr`` de sus dos hojas
``unquote``: sin la clase, ``repr`` las devuelve entrecomilladas y el cliente
recibiría la cadena literal en vez del nombre a resolver. Comparar el
``Domain`` con otro ``Domain`` sería ciego a eso.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models.ir_actions import IrActionsServer
from addons.base.models.ir_model import (
    IrModel, IrModelFields, IrModelFieldsSelection)
from orm.environments import context_scope

PARTNER = 'base.ResPartner'


def _action(**kwargs):
    kwargs.setdefault('name', 'Accion')
    kwargs.setdefault('state', 'multi')
    return IrActionsServer.objects.create(**kwargs)


def _partner_model():
    """La fila de ``ir.model`` cuyo ``name`` estos casos gobiernan.

    ``update_or_create`` y no ``get_or_create``: la fila de ``base.ResPartner``
    **ya existe** cuando estos casos corren —la siembra de la ACL la crea en
    ``0059_seed_base_security``—, así que un ``defaults=`` no llegaba a
    aplicarse nunca y el caso medía el nombre que la siembra hubiera puesto en
    vez del que declara. El montaje no controlaba lo que creía controlar.
    """
    row, _created = IrModel.objects.update_or_create(
        model=PARTNER, defaults={'name': 'Contacto'})
    return row


def _field(model_row, name, ttype='char'):
    """Ídem: la fila del campo se fuerza, no se hereda de lo ya sembrado."""
    row, _created = IrModelFields.objects.update_or_create(
        model=PARTNER, name=name,
        defaults={'model_id': model_row, 'ttype': ttype, 'state': 'base'})
    return row


@pytest.mark.django_db
class TestTheGeneratedName:
    """≙ ``_generate_action_name``: el nombre que la acción se pone sola."""

    def test_object_create_names_itself_after_the_target_model(self):
        action = _action(name='', state='object_create',
                         crud_model_id=_partner_model())

        assert action._generate_action_name() == 'Crear Contacto'

    def test_object_write_names_itself_after_the_target_model(self):
        action = _action(name='', state='object_write',
                         crud_model_id=_partner_model())

        assert action._generate_action_name() == 'Actualizar Contacto'

    def test_object_copy_without_a_record_says_so(self):
        """La fuente devuelve ``Duplicate ...`` cuando aún no hay referencia."""
        action = _action(name='', state='object_copy',
                         crud_model_id=_partner_model())

        assert action._generate_action_name() == 'Duplicar ...'

    def test_any_other_state_falls_back_to_its_label(self):
        assert _action(state='webhook')._generate_action_name() == \
            dict(IrActionsServer.STATE_CHOICES)['webhook']


@pytest.mark.django_db
class TestTheAutomaticNameSurvivesOnlyWhileNobodyRenamesIt:
    """≙ ``_compute_name``: ``was_automated`` decide si ``name`` se pisa."""

    def test_an_action_without_a_name_gets_the_generated_one(self):
        action = _action(name='', state='object_create',
                         crud_model_id=_partner_model())

        assert action.name == 'Crear Contacto'
        assert action.automated_name == 'Crear Contacto'

    def test_a_name_the_user_wrote_is_not_overwritten(self):
        action = _action(name='La mia', state='object_create',
                         crud_model_id=_partner_model())

        assert action.name == 'La mia'
        assert action.automated_name == 'Crear Contacto', \
            'el automatico se calcula igual, aunque no gane'

    def test_changing_the_state_regenerates_a_name_that_was_automatic(self):
        action = _action(name='', state='object_create',
                         crud_model_id=_partner_model())
        action.state = 'object_write'
        action.save()

        assert action.name == 'Actualizar Contacto'

    def test_changing_the_state_respects_a_name_the_user_wrote(self):
        action = _action(name='La mia', state='object_create',
                         crud_model_id=_partner_model())
        action.state = 'object_write'
        action.save()

        assert action.name == 'La mia'
        assert action.automated_name == 'Actualizar Contacto'

    def test_emptying_the_name_brings_the_automatic_one_back(self):
        """≙ ``_onchange_name``: vaciar el campo lo repuebla."""
        action = _action(name='La mia', state='object_create',
                         crud_model_id=_partner_model())
        action.name = ''
        action._onchange_name()

        assert action.name == 'Crear Contacto'

    def test_the_depends_lists_what_the_source_lists(self):
        declared = IrActionsServer._name_depends()

        assert declared == ['state', 'crud_model_id', 'resource_ref']


@pytest.mark.django_db
class TestTheDerivedSurface:
    """Los campos que la fuente declara ``compute`` y aquí son no persistidos."""

    def test_allowed_states_lists_every_state_of_the_selection(self):
        assert _action().allowed_states == \
            [value for value, __ in IrActionsServer.STATE_CHOICES]

    def test_available_model_ids_are_the_reflected_models(self):
        _partner_model()

        assert _partner_model().pk in _action().available_model_ids

    def test_crud_model_name_follows_its_foreign_key(self):
        """≙ ``related='crud_model_id.model'``."""
        action = _action(crud_model_id=_partner_model())

        assert action.crud_model_name == PARTNER

    def test_crud_model_name_is_empty_without_a_target(self):
        assert _action().crud_model_name is False

    def test_update_field_type_follows_its_foreign_key(self):
        """≙ ``related='update_field_id.ttype'``."""
        model_row = _partner_model()
        action = _action(update_field_id=_field(model_row, 'name'))

        assert action.update_field_type == 'char'


@pytest.mark.django_db
class TestWhichValueFieldTheFormShows:
    """≙ ``_compute_value_field_to_show``: seis ramas, una por tipo."""

    def _with_field(self, ttype):
        model_row = _partner_model()
        return _action(update_field_id=_field(model_row, f'f_{ttype}', ttype))

    def test_a_sequence_shows_the_sequence(self):
        action = _action(evaluation_type='sequence')

        assert action.value_field_to_show == 'sequence_id'

    def test_a_relational_field_shows_the_reference(self):
        assert self._with_field('many2one').value_field_to_show == 'resource_ref'

    def test_a_selection_field_shows_the_selection(self):
        assert self._with_field('selection').value_field_to_show == \
            'selection_value'

    def test_a_boolean_field_shows_the_boolean(self):
        assert self._with_field('boolean').value_field_to_show == \
            'update_boolean_value'

    def test_an_html_field_shows_the_html(self):
        assert self._with_field('html').value_field_to_show == 'html_value'

    def test_anything_else_shows_the_plain_value(self):
        assert self._with_field('char').value_field_to_show == 'value'


@pytest.mark.django_db
class TestTheChildrenDomain:
    """≙ ``_get_children_domain``: dos hojas por resolver, una constante."""

    def test_the_two_unquoted_leaves_come_out_without_quotes(self):
        """Sin ``unquote`` el cliente recibiria la cadena literal.

        Es el control que discrimina: ``repr('model_id')`` trae comillas y
        ``repr(unquote('model_id'))`` no. Comparar dos ``Domain`` entre si
        seria ciego a la diferencia.

        Se mide la posicion del **valor**, no la del campo. Una hoja es
        ``(campo, operador, valor)`` y el campo es una cadena normal: sus
        comillas son correctas y salen igual en la fuente. Afirmar que
        ``"'model_id'"`` no aparece en ninguna parte medía las dos posiciones
        a la vez y no podia pasar nunca.
        """
        rendered = repr(IrActionsServer._get_children_domain())

        assert "'=', model_id)" in rendered
        assert "'!=', id)" in rendered
        assert "'=', 'model_id')" not in rendered
        assert "'!=', 'id')" not in rendered

    def test_it_only_offers_actions_that_are_not_already_children(self):
        rendered = repr(IrActionsServer._get_children_domain())

        assert 'parent_id' in rendered


@pytest.mark.django_db
class TestThePythonCodeIsCheckedWithoutRunningIt:
    """≙ ``_check_python_code``: valida, nunca ejecuta."""

    def test_valid_code_is_accepted(self):
        _action(state='code', code='x = 1\ny = x + 1\n')

    def test_broken_syntax_is_refused(self):
        with pytest.raises(ValidationError):
            _action(state='code', code='if True\n    pass\n')

    def test_the_check_does_not_execute_what_it_validates(self):
        """El control que discrimina validar de ejecutar.

        El codigo levantaria al ejecutarse; si el guardian lo corriera, el
        caso veria ese error y no el silencio de una validacion limpia.
        """
        _action(state='code', code='raise Exception("no debe correr")\n')


@pytest.mark.django_db
class TestTheCopyIsMarkedAsOne:
    """≙ ``copy_data``: el duplicado se nombra como tal.

    Se indexa como ``dict`` y no como lista porque ésa es la forma que
    ``CopyMixin.copy_data`` declara en este árbol: allá ``self`` es un
    recordset y responde uno por registro; aquí una instancia **es** un
    registro. Un ``[0]`` aquí mediría la forma de la fuente, no la nuestra.
    """

    def test_the_duplicate_says_it_is_a_copy(self):
        action = _action(name='Original')

        assert action.copy_data()['name'] == 'Original (copia)'

    def test_an_explicit_name_wins_over_the_suffix(self):
        action = _action(name='Original')

        assert action.copy_data({'name': 'Otro'})['name'] == 'Otro'


@pytest.mark.django_db
class TestTheOnchangeSetters:
    """≙ ``_set_crud_model_id``, ``_set_resource_ref``, ``_set_selection_value``."""

    def test_a_link_field_of_another_model_is_dropped(self):
        model_row = _partner_model()
        other, _c = IrModel.objects.get_or_create(
            model='base.ResCountry', defaults={'name': 'Pais'})
        link = _field(model_row, 'ajeno', 'many2one')
        action = _action(model_name=PARTNER, crud_model_id=other,
                         link_field_id=link)

        action._set_crud_model_id()

        assert action.link_field_id is None

    def test_the_reference_is_copied_into_the_value(self):
        model_row = _partner_model()
        action = _action(update_field_id=_field(model_row, 'padre', 'many2one'),
                         resource_ref_id=42)

        action._set_resource_ref()

        assert action.value == '42'

    def test_the_selection_is_copied_into_the_value(self):
        model_row = _partner_model()
        field_row = _field(model_row, 'tipo', 'selection')
        # ``bulk_create`` y no ``create``: el campo es **base**, y la guarda
        # de ``save`` cierra el alta interactiva sobre un campo base — igual
        # que la fuente. El reflejo escribe por esta misma vía.
        [choice] = IrModelFieldsSelection.objects.bulk_create([
            IrModelFieldsSelection(
                field_id=field_row, value='delivery', name='Entrega',
                sequence=1)])
        action = _action(update_field_id=field_row, selection_value=choice)

        action._set_selection_value()

        assert action.value == 'delivery'


@pytest.mark.django_db
class TestTheDefaultUpdatePath:
    """≙ ``_default_update_path``: el primer campo sensato del modelo."""

    def test_without_a_default_model_in_context_it_is_empty(self):
        assert IrActionsServer._default_update_path() == ''

    def test_it_picks_the_first_sensible_field_the_model_has(self):
        """``user`` y no ``active``: la lista se recorre **en su orden**.

        ``user`` es el cuarto candidato traducido (``user_id`` allá,
        ``res_partner.py:231``, ``readonly=False, store=True``) y ``active`` el
        último. Esperar ``active`` medía el final de la lista, que es lo que
        devuelve un modelo que no tiene ninguno de los cuatro anteriores.
        """
        model_row = _partner_model()

        with context_scope(default_model_id=model_row.pk):
            assert IrActionsServer._default_update_path() == 'user'

    def test_the_country_state_fk_does_not_pass_as_the_workflow_state(self):
        """El control que discrimina la colisión que el sufijo ``_id`` produce.

        ``state`` de la lista nombra el **estado de flujo** —``Selection`` en
        98 de las 100 declaraciones de ``odoo19c``—, pero al quitar el sufijo
        el ``state_id`` de ``res.partner`` pasa a llamarse igual. Sin el
        discriminador de relación, con los cuatro primeros candidatos fuera de
        alcance este caso devolvería la entidad federativa.
        """
        model_row = _partner_model()
        without_the_first_four = [c for c in IrActionsServer.SENSIBLE_DEFAULT_FIELDS
                          if c in ('state', 'active')]

        with context_scope(default_model_id=model_row.pk):
            original = IrActionsServer.SENSIBLE_DEFAULT_FIELDS
            IrActionsServer.SENSIBLE_DEFAULT_FIELDS = without_the_first_four
            try:
                assert IrActionsServer._default_update_path() == 'active'
            finally:
                IrActionsServer.SENSIBLE_DEFAULT_FIELDS = original


@pytest.mark.django_db
class TestTheTargetModelSelection:
    """≙ ``_selection_target_model``: los pares del ``Reference``."""

    def test_every_reflected_model_is_offered(self):
        _partner_model()
        pairs = dict(IrActionsServer._selection_target_model())

        assert pairs[PARTNER] == 'Contacto'
