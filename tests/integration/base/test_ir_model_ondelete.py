"""Tests — la política de borrado de un valor de selección (``_process_ondelete``).

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:1749-1822``
(``_process_ondelete`` y su ``safe_write``) y de
``odoo19c: odoo/orm/fields_selection.py:39-57,129-163`` (las cinco políticas y
su validación).

Un valor de selección que desaparece deja huérfanas las filas que lo
guardaban. La política dice qué hacer con ellas, y la declara quien amplió el
vocabulario, junto a su ``selection_add``.

La premisa que este archivo corrige
====================================

El método estuvo declarado BLOQUEADO *"por ``fields.Selection``, que no acepta
ese parámetro"*. Esa premisa nombraba el receptor equivocado: la fuente declara
``ondelete=`` **junto a** ``selection_add=`` en la misma redeclaración, y el
``selection_add`` de este árbol no es un parámetro de campo sino
``extend_model(selection_add=…)`` / ``extend_selection_choices``. Ahí se
construyó el receptor.

Qué haría fallar a cada control
--------------------------------

``TestThePolicies``
    Las cinco de la fuente, una por caso. Lo haría fallar aplicar la misma a
    todas: cada caso mide un efecto **distinto** sobre la misma fila.

``TestThePolicies.test_a_value_without_a_declared_policy_is_left_alone``
    CONTROL: el método sólo actúa sobre valores que vienen de una ampliación.
    Sin él, una implementación que limpiara **todo** valor borrado pasaría los
    otros cinco igual y borraría datos que nadie le pidió tocar.

``TestTheDefault``
    Todo valor nuevo que el mapa no nombre recibe ``'set null'``. Lo haría
    fallar dejarlo sin política: el valor quedaría huérfano en silencio.

``TestTheValidation``
    Las cuatro comprobaciones de la fuente. Cada caso apunta a un mensaje
    distinto; el control es que una política **válida** no levanta.

``TestSafeWrite``
    CONTROL del respaldo: con el ``save()`` del modelo levantando, la
    escritura tiene que llegar igual por debajo del ORM. Sin ese caso, el
    ``except`` no se ejerce nunca y podría estar roto sin que nadie lo note.
"""
import pytest
from django.db.models.fields import NOT_PROVIDED

from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.ir_model import (
    IrModel, IrModelFields, IrModelFieldsSelection)
from exceptions import UserError
from orm.model_classes import (ONDELETE_DEFAULT, check_ondelete_policies,
                               extend_selection_choices)

pytestmark = pytest.mark.integration

#: El modelo sobre el que se mide.
#:
#: Se elige ``act_window.target`` por dos razones medidas, no por comodidad:
#:
#: 1. La fuente **no** lo declara requerido
#:    (``odoo19c: odoo/addons/base/models/ir_actions.py:317`` — un
#:    ``fields.Selection`` con ``default="current"`` y sin ``required``), asi
#:    que el camino de la politica por defecto ``'set null'`` se puede medir.
#: 2. Su ``save()`` no guarda el valor anterior. ``ir.model.fields.ttype``, el
#:    primer candidato, falla las dos: es ``required=True`` alli (``:871`` aqui,
#:    ya declarado) y su ``save()`` levanta *"Cambiar el tipo de un campo no
#:    esta soportado"*, asi que ninguna victima se puede preparar.
MODEL_LABEL = 'base.IrActionsActWindow'
FIELD_NAME = 'target'


def _reflected_value(value, name=FIELD_NAME, model_label=MODEL_LABEL):
    """La fila de ``ir.model.fields.selection`` que apunta al campo real.

    Se arma en tres pasos y el ORDEN importa, porque las guardas del modelo
    —fieles a la fuente— se cierran entre si:

    1. el campo nace ``state='manual'`` con prefijo ``x_``, que es lo unico
       que la restriccion ``ir_model_fields_name_manual_field`` admite;
    2. el valor se crea mientras el campo sigue manual — el ``save()`` de
       ``IrModelFieldsSelection`` rehusa si el campo ya es base;
    3. el campo pasa a ``name=<real>, state='base'`` con un ``update()`` de
       queryset, que no pasa por ``save()``.

    En produccion nadie escribe estas filas a mano: las emite el reflejo
    (``_reflect_model``/``_update_selection``). El paso 3 es el mismo patron
    que ya usa ``test_ir_model_reflect_selection.py:125``.
    """
    model_row, _ = IrModel.objects.get_or_create(
        model=model_label, defaults={'name': 'Ventana de accion'})
    field_row = IrModelFields.objects.create(
        model=model_label, name=f'x_{name}_{value}',
        field_description='Ventana destino', ttype='selection',
        state='manual', model_id=model_row)
    row = IrModelFieldsSelection.objects.create(
        field_id=field_row, value=value, name=value.title(), sequence=0)
    IrModelFields.objects.filter(pk=field_row.pk).update(
        name=name, state='base')
    # El ``update()`` no toca el objeto en memoria, y ``row.field_id`` guarda
    # la instancia cacheada con el nombre viejo. Sin este refresco
    # ``_process_ondelete`` buscaria un campo ``x_target_<valor>`` que el
    # modelo no tiene, y saldria sin hacer nada — en silencio.
    row.refresh_from_db()
    return row


def _victim(target, name):
    """Un registro real que guarda el valor que va a desaparecer."""
    return IrActionsActWindow.objects.create(
        name=name, type='ir.actions.act_window', res_model='base.ResPartner',
        target=target)


@pytest.fixture
def target(db):
    """Un campo ``Selection`` real con su vocabulario restaurado al salir.

    El campo es de clase: ampliarlo sin restaurar contaminaría a los demás
    casos y a los demás archivos de la suite.
    """
    field = IrActionsActWindow._meta.get_field(FIELD_NAME)
    choices_before = list(field.choices)
    ondelete_before = getattr(field, 'ondelete', None)
    default_before = field.default
    yield field
    field.choices = choices_before
    field.default = default_before
    if ondelete_before is None:
        if hasattr(field, 'ondelete'):
            del field.ondelete
    else:
        field.ondelete = ondelete_before


class TestThePolicies:
    """≙ las cinco de ``_process_ondelete`` (``odoo19c: :1806-1821``)."""

    def test_set_null_empties_the_field(self, db, target):
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_nulo', 'Nulo')],
                                 ondelete={'x_nulo': 'set null'})
        victim = _victim('x_nulo', 'Victima nulo')
        _reflected_value('x_nulo').delete(at_uninstall=True)
        victim.refresh_from_db()
        assert victim.target is None

    def test_cascade_deletes_the_rows(self, db, target):
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_cascada', 'Cascada')],
                                 ondelete={'x_cascada': 'cascade'})
        pk = _victim('x_cascada', 'Victima cascada').pk
        _reflected_value('x_cascada').delete(at_uninstall=True)
        assert not IrActionsActWindow.objects.filter(pk=pk).exists()

    def test_set_default_takes_the_declared_default(self, db, target):
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_defecto', 'Defecto')],
                                 ondelete={'x_defecto': 'set default'})
        victim = _victim('x_defecto', 'Victima defecto')
        _reflected_value('x_defecto').delete(at_uninstall=True)
        victim.refresh_from_db()
        assert victim.target == 'current'   # el default declarado del campo

    def test_set_value_takes_the_named_value(self, db, target):
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_valor', 'Valor')],
                                 ondelete={'x_valor': 'set new'})
        victim = _victim('x_valor', 'Victima valor')
        _reflected_value('x_valor').delete(at_uninstall=True)
        victim.refresh_from_db()
        assert victim.target == 'new'

    def test_a_callable_receives_the_records(self, db, target):
        seen = {}

        def custom(records):
            seen['count'] = records.count()

        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_invocable', 'Invocable')],
                                 ondelete={'x_invocable': custom})
        victim = _victim('x_invocable', 'Victima invocable')
        _reflected_value('x_invocable').delete(at_uninstall=True)
        assert seen['count'] == 1
        victim.refresh_from_db()
        assert victim.target == 'x_invocable'

    def test_a_value_without_a_declared_policy_is_left_alone(self, db, target):
        """CONTROL: sólo actúa sobre lo que vino de una ampliación.

        ``target='new'`` es del vocabulario original, no de un
        ``selection_add``, así que borrar su fila de ``ir.model.fields.selection``
        no debe tocar a nadie.
        """
        victim = _victim('new', 'Victima intacta')
        _reflected_value('new').delete(at_uninstall=True)
        victim.refresh_from_db()
        assert victim.target == 'new'


class TestTheUninstallFlag:
    """≙ ``@api.ondelete(at_uninstall=False)`` (``odoo19c: :1723``)."""

    def test_a_hand_delete_of_a_base_value_is_refused(self, db, target):
        """CONTROL POSITIVO de la guarda: sin el, ``at_uninstall`` seria una
        bandera que no apaga nada y los demas casos pasarian igual."""
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_a_mano', 'A mano')],
                                 ondelete={'x_a_mano': 'cascade'})
        with pytest.raises(UserError, match='campo base'):
            _reflected_value('x_a_mano').delete()

    def test_the_policy_does_not_run_when_the_guard_refuses(self, db, target):
        """La guarda es lo PRIMERO: si rehusa, la politica no toca nada.

        Es el orden de la fuente, y lo que hace que un borrado a mano sea
        inocuo en vez de destructivo a medias.
        """
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_intacto', 'Intacto')],
                                 ondelete={'x_intacto': 'cascade'})
        victim = _victim('x_intacto', 'Sobrevive a la guarda')
        with pytest.raises(UserError):
            _reflected_value('x_intacto').delete()
        victim.refresh_from_db()
        assert victim.target == 'x_intacto'


class TestTheDefault:
    """≙ ``ondelete.setdefault(key, 'set null')`` (``odoo19c: :131-133``)."""

    def test_a_new_value_the_map_does_not_name_gets_set_null(self, db, target):
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_sin_mapa', 'Sin mapa')])
        assert target.ondelete['x_sin_mapa'] == ONDELETE_DEFAULT

    def test_a_second_extension_does_not_erase_the_first(self, db, target):
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_uno', 'Uno')],
                                 ondelete={'x_uno': 'cascade'})
        extend_selection_choices(IrActionsActWindow, FIELD_NAME,
                                 [('x_dos', 'Dos')],
                                 ondelete={'x_dos': 'cascade'})
        assert target.ondelete['x_uno'] == 'cascade'
        assert target.ondelete['x_dos'] == 'cascade'


class TestTheValidation:
    """≙ ``check_ondelete_policies`` (``odoo19c: :134-163``)."""

    def test_set_default_without_a_default_is_refused(self, db, target):
        target.default = NOT_PROVIDED
        with pytest.raises(ValueError, match='set default'):
            check_ondelete_policies(target, {'x': 'set default'}, ['x'],
                                    {'x', 'new'})

    def test_set_value_pointing_outside_the_selection_is_refused(self, db, target):
        with pytest.raises(ValueError, match='set %'):
            check_ondelete_policies(target, {'x': 'set inexistente'}, ['x'],
                                    {'x', 'new'})

    def test_an_unknown_policy_is_refused(self, db, target):
        with pytest.raises(ValueError, match='no es valida'):
            check_ondelete_policies(target, {'x': 'incinerar'}, ['x'],
                                    {'x', 'new'})

    def test_a_valid_policy_does_not_raise(self, db, target):
        """CONTROL: sin él, una validación que rechazara todo pasaría los tres."""
        check_ondelete_policies(target, {'x': 'cascade'}, ['x'], {'x', 'new'})
        check_ondelete_policies(target, {'x': 'set new'}, ['x'], {'x', 'new'})
        check_ondelete_policies(target, {'x': lambda rows: None}, ['x'],
                                {'x', 'new'})


class TestSafeWrite:
    """≙ la clausura ``safe_write`` (``odoo19c: :1751-1773``)."""

    def test_the_write_goes_through_the_orm_when_it_can(self, db, target):
        victim = _victim('current', 'Victima orm')
        rows = IrActionsActWindow.objects.filter(pk=victim.pk)
        IrModelFieldsSelection._safe_write(rows, 'name', 'Renombrada')
        victim.refresh_from_db()
        assert victim.name == 'Renombrada'

    def test_it_falls_back_below_the_orm_when_save_raises(self, db, target,
                                                          monkeypatch):
        """CONTROL del respaldo: con ``save()`` levantando, el valor llega igual.

        Es el caso que la fuente describe verbatim: *"going through the ORM
        failed, probably because of an exception in an override or possibly a
        constraint"*. Sin este caso el ``except`` no se ejerce nunca.
        """
        victim = _victim('current', 'Victima abajo')

        def explode(self, *args, **kwargs):
            raise RuntimeError('un override que levanta')

        monkeypatch.setattr(IrActionsActWindow, 'save', explode)
        rows = IrActionsActWindow.objects.filter(pk=victim.pk)
        IrModelFieldsSelection._safe_write(rows, 'name', 'Abajo')
        monkeypatch.undo()
        victim.refresh_from_db()
        assert victim.name == 'Abajo'

    def test_an_empty_queryset_is_a_no_op(self, db, target):
        rows = IrActionsActWindow.objects.filter(name='x_no_existe_nadie')
        IrModelFieldsSelection._safe_write(rows, 'name', 'X')
