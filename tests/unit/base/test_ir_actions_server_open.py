"""``ir.actions.server`` — el enlace ``parent`` y sus dos acciones de apertura.

Porta ``odoo19c: odoo/addons/base/models/ir_actions.py:648`` (el campo) y
``:1328-1344`` (los dos ``action_open_*``), LGPL-3. Antes de este pase los dos
metodos existian en ``ir_cron.py`` como firmas que delegaban en un modelo que
no tenia a que apuntar: el docstring declaraba el bloqueo y citaba su sucesor,
que es esta tarea.

El control que puede fallar
---------------------------

**El caso negativo de ``action_open_scheduled_action``.** La fuente indexa
``self.ir_cron_ids.ids[0]`` y reventaria con ``IndexError`` sobre una action
sin cron; aqui devuelve ``None``, que es divergencia declarada. Sustituyendo
la guarda ``if cron is None`` por un ``self.crons.first().pk`` pelado, esta
suite pasa de **8 passed** a **1 failed, 7 passed**: cae
``test_an_action_without_a_cron_opens_nothing``, el unico caso cuyo veredicto
depende de esa rama. Los otros siete crean su cron, asi que sobrevivirian —
y ahi esta el punto: sin ese caso, la guarda podria desaparecer sin que la
suite se entere.

**El inverso ``crons`` ve a los inactivos.** La fuente lo pide explicitamente
con ``context={'active_test': False}`` (``:641``). En Django lo da el manager
por defecto sin hacer nada, asi que el caso existe para que un manager con
filtro anadido despues no lo rompa en silencio.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from addons.base.models import IrActionsServer, IrCron
from orm.environments import sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def _as_superuser():
    """≙ ``TransactionCase`` de la fuente, que corre como superusuario:
    ``ir.actions.server`` es ``BaseModel`` y sólo ``group_system`` lo lee
    (``odoo19c: odoo/addons/base/security/ir.model.access.csv:107``).
    Precedente: ``test_copy_follows_the_one2many_copy_flag.py``."""
    with sudo():
        yield


@pytest.fixture
def action():
    return IrActionsServer.objects.create(
        name='Accion de prueba',
        state='code',
        model_name='ir.config_parameter',
        method_name='noop_test',
    )


@pytest.fixture
def cron(action):
    return IrCron.objects.create(
        ir_actions_server=action,
        interval_number=1,
        interval_type='days',
        nextcall=timezone.now() - timedelta(minutes=1),
        active=True,
    )


# --------------------------------------------------------------------------
# El campo parent — ≙ parent_id (:648) y su inverso child_ids (:649-650)
# --------------------------------------------------------------------------


def test_an_action_can_declare_its_parent(action):
    child = IrActionsServer.objects.create(
        name='Hija',
        state='code',
        model_name='ir.config_parameter',
        method_name='noop_test',
        parent_id=action,
    )
    assert child.parent_id == action
    assert list(action.child_ids) == [child]


def test_the_parent_is_optional(action):
    """
    La fuente lo declara sin ``required``: una accion suelta no tiene padre.
    Sobre ``BaseModel`` el ``Many2one`` vacío es un recordset vacío.
    """
    assert not action.parent_id


def test_deleting_the_parent_takes_the_children(action):
    """≙ ``ondelete='cascade'`` de la fuente, conservado verbatim."""
    child = IrActionsServer.objects.create(
        name='Hija',
        state='code',
        model_name='ir.config_parameter',
        method_name='noop_test',
        parent_id=action,
    )
    action.delete()
    assert not IrActionsServer.objects.filter(pk=child.pk).exists()


# --------------------------------------------------------------------------
# action_open_parent_action — ≙ :1328-1335
# --------------------------------------------------------------------------


def test_open_parent_points_at_the_parent(action):
    child = IrActionsServer.objects.create(
        name='Hija',
        state='code',
        model_name='ir.config_parameter',
        method_name='noop_test',
        parent_id=action,
    )
    assert child.action_open_parent_action() == {
        'type': 'ir.actions.act_window',
        'target': 'current',
        'views': [[False, 'form']],
        'res_model': 'ir.actions.server',
        'res_id': action.pk,
    }


def test_the_cron_delegates_to_its_action(cron, action):
    """≙ ``ir_cron.py:889-891``: el cron no arma el descriptor, delega."""
    parent_action = IrActionsServer.objects.create(
        name='Padre',
        state='code',
        model_name='ir.config_parameter',
        method_name='noop_test',
    )
    action.parent_id = parent_action
    action.save(update_fields=['parent_id'])
    assert cron.action_open_parent_action()['res_id'] == parent_action.pk


# --------------------------------------------------------------------------
# action_open_scheduled_action — ≙ :1337-1344
# --------------------------------------------------------------------------


def test_open_scheduled_points_at_the_cron(action, cron):
    assert action.action_open_scheduled_action() == {
        'type': 'ir.actions.act_window',
        'target': 'current',
        'views': [[False, 'form']],
        'res_model': 'ir.cron',
        'res_id': cron.pk,
    }


def test_an_action_without_a_cron_opens_nothing(action):
    """Divergencia declarada: la fuente indexaria ``[0]`` y reventaria."""
    assert action.action_open_scheduled_action() is None


def test_the_inverse_sees_an_inactive_cron(action, cron):
    """≙ ``context={'active_test': False}`` (``:641``), gratis en Django."""
    cron.active = False
    cron.save(update_fields=['active'])
    assert action.action_open_scheduled_action()['res_id'] == cron.pk


def test_parent_id_keeps_the_source_name():
    """``parent_id`` (``odoo19c: ir_actions.py:648``) con su nombre y su
    columna, y ``child_ids`` como su inverso."""
    field = IrActionsServer._meta.get_field('parent_id')
    assert (field.column, field.related_model) == (
        'parent_id', IrActionsServer)
    names = {f.name for f in IrActionsServer._meta.get_fields()}
    assert 'parent' not in names
    assert IrActionsServer._fields['child_ids'].inverse_name == 'parent_id'
