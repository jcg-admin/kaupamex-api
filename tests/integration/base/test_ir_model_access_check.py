"""Tests — la ACL como PUERTA, no sólo como dato (``ir.model.access.check``).

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:2155``
(``check``), ``:2134`` (``_get_allowed_models``) y ``:2169``
(``_make_access_error``).

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

``_get_allowed_models(mode)`` consulta ``ir_model_access`` unida a ``ir_model``
y devuelve los modelos con una fila **activa**, con ``perm_<mode>`` verdadero,
y cuyo ``group_id`` sea **nulo** (global) o esté entre los grupos del usuario.
De ahí se sigue el invariante que más importa: **un modelo SIN ninguna fila de
ACL queda denegado**. Fail-closed por construcción, no por una guarda escrita
aparte.

``check`` antepone dos cosas: bajo ``su`` devuelve ``True`` sin consultar nada
(``if self.env.su: return True``), y con ``raise_exception`` levanta el error
compuesto en vez de devolver ``False``.

Qué haría fallar a cada control
--------------------------------

``TestAllowedModels.test_a_model_without_any_acl_row_is_denied``
    El eje. Lo haría fallar leer la ausencia de fila como permiso — que es lo
    que hacía este árbol antes de esta tarea, porque la tabla estaba vacía y
    nadie la consultaba.

``TestCheck.test_a_row_for_another_mode_does_not_grant_this_one``
    CONTROL de discriminación: sin él, una consulta que ignorara
    ``perm_<mode>`` pasaría los demás casos igual.

``TestCheck.test_an_inactive_row_grants_nothing``
    CONTROL: ``active`` es columna portada; si nadie la consulta, desactivar
    una ACL no desactiva nada (la clase de :ref:`h-api-836`).

``TestCheck.test_under_su_everything_is_allowed``
    CONTROL del bypass. Lo haría fallar consultar la tabla bajo ``su``.
"""
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.res_groups import ResGroups
from exceptions import AccessError
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.integration

#: Un modelo de ``base`` **que el sembrador NO cubre**, para que estos casos
#: midan la mecánica de ``check`` y no el contenido de la semilla. Si algún día
#: entra en la ACL de ``base``, estos casos empiezan a medir dos cosas y hay
#: que mover el ancla — que es justo lo que pasó con ``ir.ui.view.custom``.
MODEL_LABEL = 'base.ResDeviceLog'
MODEL_DOTTED = 'res.device.log'


def _acl(mode='read', group=None, active=True, name='acl de prueba'):
    """Declara una fila de ACL para ``MODEL_LABEL`` con un solo permiso."""
    row, _ = IrModel.objects.get_or_create(
        model=MODEL_LABEL, defaults={'name': 'Registro de dispositivo'})
    return IrModelAccess.objects.create(
        name=name, model_id=row, group_id=group, active=active,
        **{f'perm_{mode}': True})


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password='AclPrueba123!')


class TestAllowedModels:
    """≙ ``_get_allowed_models`` — el conjunto, no el veredicto."""

    def test_a_model_without_any_acl_row_is_denied(self, db):
        who = _user('acl.sin.fila@kaupamex.mx')
        assert MODEL_LABEL not in IrModelAccess._get_allowed_models(
            'read', user=who)

    def test_a_global_row_puts_the_model_in_the_set(self, db):
        _acl('read', group=None)
        who = _user('acl.global.set@kaupamex.mx')
        assert MODEL_LABEL in IrModelAccess._get_allowed_models(
            'read', user=who)

    def test_a_group_row_only_counts_for_its_members(self, db):
        group = ResGroups.objects.create(name='lectores', user_type='internal')
        _acl('read', group=group)
        outside = _user('acl.fuera.set@kaupamex.mx')
        assert MODEL_LABEL not in IrModelAccess._get_allowed_models(
            'read', user=outside)
        outside.group_ids.add(group)
        assert MODEL_LABEL in IrModelAccess._get_allowed_models(
            'read', user=outside)

    def test_an_invalid_mode_raises(self, db):
        with pytest.raises(ValueError):
            IrModelAccess._get_allowed_models('browse')


class TestTheCacheIsInvalidatedByItsOwnTable:
    """≙ ``call_cache_clearing_methods`` (``odoo19c: :2196-2199``).

    El conjunto de modelos permitidos se memoriza en la familia ``stable``,
    igual que en la fuente. Una caché sin invalidador concede lo que ya se
    revocó, que es el defecto que la tarea #58 midió en ``_get_group_ids``:
    estos dos casos son el control de que el invalidador corre.

    Medido con la guarda anulada —los dos ``call_cache_clearing_methods`` de
    :meth:`IrModelAccess.save` y :meth:`IrModelAccess.delete` sustituidos por
    ``pass``—: la suite de este archivo pasa de **23 passed** a **3 failed, 20
    passed**. Caen estos dos y
    ``TestCheck.test_without_a_user_only_global_rows_apply``, que también lee
    después de escribir; los otros veinte no dependen del invalidador. Sin
    memoización los tres pasan igual, porque cada lectura vuelve a la tabla.
    """

    def test_a_row_created_after_a_negative_read_grants(self, db):
        who = _user('acl.cache.alta@kaupamex.mx')
        assert MODEL_LABEL not in IrModelAccess._get_allowed_models(
            'read', user=who)
        _acl('read', group=None)
        assert MODEL_LABEL in IrModelAccess._get_allowed_models(
            'read', user=who)

    def test_a_row_deleted_after_a_positive_read_stops_granting(self, db):
        row = _acl('read', group=None)
        who = _user('acl.cache.baja@kaupamex.mx')
        assert MODEL_LABEL in IrModelAccess._get_allowed_models(
            'read', user=who)
        row.delete()
        assert MODEL_LABEL not in IrModelAccess._get_allowed_models(
            'read', user=who)


class TestCheck:
    """≙ ``check(model, mode, raise_exception)`` — el veredicto."""

    def test_a_model_without_any_acl_row_is_denied(self, db):
        who = _user('acl.check.sin@kaupamex.mx')
        assert IrModelAccess.check(
            MODEL_LABEL, 'read', raise_exception=False, user=who) is False

    def test_it_raises_by_default(self, db):
        who = _user('acl.check.raise@kaupamex.mx')
        with pytest.raises(AccessError):
            IrModelAccess.check(MODEL_LABEL, 'read', user=who)

    def test_a_global_row_grants_it(self, db):
        _acl('read', group=None)
        who = _user('acl.check.global@kaupamex.mx')
        assert IrModelAccess.check(MODEL_LABEL, 'read', user=who) is True

    def test_a_row_for_another_mode_does_not_grant_this_one(self, db):
        """CONTROL — sin él, ignorar ``perm_<mode>`` pasaría igual."""
        _acl('write', group=None)
        who = _user('acl.check.otromodo@kaupamex.mx')
        assert IrModelAccess.check(
            MODEL_LABEL, 'read', raise_exception=False, user=who) is False
        assert IrModelAccess.check(MODEL_LABEL, 'write', user=who) is True

    def test_an_inactive_row_grants_nothing(self, db):
        """CONTROL — ``active`` es columna portada; alguien tiene que leerla."""
        _acl('read', group=None, active=False)
        who = _user('acl.check.inactiva@kaupamex.mx')
        assert IrModelAccess.check(
            MODEL_LABEL, 'read', raise_exception=False, user=who) is False

    def test_under_su_everything_is_allowed(self, db):
        """CONTROL del bypass — la fuente ni consulta la tabla bajo ``su``."""
        who = _user('acl.check.su@kaupamex.mx')
        with sudo():
            assert IrModelAccess.check(MODEL_LABEL, 'unlink', user=who) is True

    def test_the_dotted_reference_name_also_resolves(self, db):
        """El llamador puede nombrar el modelo como lo nombra la fuente.

        Este árbol guarda el label de Django en ``ir_model.model`` (lo dice su
        ``help_text`` y de ello depende ``IrModel.django_model``); la fuente usa
        el nombre punteado. ``check`` normaliza en la puerta con
        ``orm.registry``, así que el llamador puede escribir cualquiera de los
        dos y leer igual que su fuente.
        """
        _acl('read', group=None)
        who = _user('acl.check.punteado@kaupamex.mx')
        assert IrModelAccess.check(MODEL_DOTTED, 'read', user=who) is True

    def test_without_a_user_only_global_rows_apply(self, db):
        """Sin usuario en contexto no hay grupos: sólo la ACL global abre."""
        group = ResGroups.objects.create(name='sin actor', user_type='internal')
        _acl('read', group=group)
        assert IrModelAccess.check(
            MODEL_LABEL, 'read', raise_exception=False) is False
        _acl('read', group=None, name='global')
        assert IrModelAccess.check(MODEL_LABEL, 'read') is True

    def test_the_user_comes_from_the_environment_when_not_given(self, db):
        """≙ ``self.env.user`` — el llamador no tiene que pasarlo."""
        _acl('read', group=None)
        who = _user('acl.check.entorno@kaupamex.mx')
        with user_scope(who.pk):
            assert IrModelAccess.check(MODEL_LABEL, 'read') is True


class TestAccessError:
    """≙ ``_make_access_error`` — el mensaje que explica el rechazo."""

    def test_the_message_names_the_model_and_the_operation(self, db):
        who = _user('acl.error.nombra@kaupamex.mx')
        with pytest.raises(AccessError) as caught:
            IrModelAccess.check(MODEL_LABEL, 'write', user=who)
        message = str(caught.value)
        assert MODEL_LABEL in message
        assert 'modificar' in message.lower()

    def test_it_lists_the_groups_that_would_allow_it(self, db):
        group = ResGroups.objects.create(
            name='editores de vista', user_type='internal')
        _acl('write', group=group)
        who = _user('acl.error.grupos@kaupamex.mx')
        with pytest.raises(AccessError) as caught:
            IrModelAccess.check(MODEL_LABEL, 'write', user=who)
        assert 'editores de vista' in str(caught.value)

    def test_it_says_so_when_no_group_allows_it(self, db):
        """CONTROL — la fuente distingue los dos mensajes."""
        who = _user('acl.error.ninguno@kaupamex.mx')
        with pytest.raises(AccessError) as caught:
            IrModelAccess.check(MODEL_LABEL, 'write', user=who)
        assert 'ningún grupo' in str(caught.value).lower()


class TestSeededAcl:
    """La ACL sembrada — ``ir.ui.view`` es la que el adjunto consulta.

    ≙ ``odoo19c: odoo/addons/base/security/ir.model.access.csv:35-36``: una
    fila global con los cuatro permisos en 0, y una de ``group_system`` con los
    cuatro en 1. Es decir: **escribir vistas es del grupo de sistema y de nadie
    más**, que es exactamente lo que ``_can_write_views`` necesita preguntar.
    """

    def test_a_plain_user_cannot_write_views(self, db):
        who = _user('acl.vista.llano@kaupamex.mx')
        assert IrModelAccess.check(
            'ir.ui.view', 'write', raise_exception=False, user=who) is False

    def test_the_system_group_can(self, db):
        system = apps.get_model('base', 'IrModelData').objects.filter(
            module='base', name='group_system').first()
        assert system is not None, 'la semilla de grupos no corrió'
        who = _user('acl.vista.sistema@kaupamex.mx')
        who.group_ids.add(ResGroups.objects.get(pk=system.res_id))
        assert IrModelAccess.check('ir.ui.view', 'write', user=who) is True

    def test_the_global_row_grants_nothing_not_even_read(self, db):
        """CONTROL — la fila global de la fuente lleva los cuatro ceros.

        ``ir.model.access.csv:35`` declara ``"…","model_ir_ui_view",,0,0,0,0``:
        existe la fila y **no concede nada**. Un sembrador que la escribiera con
        ``perm_read=True`` —el reflejo de *«leer una vista lo puede todo el
        mundo»*— pasaría los otros dos casos de esta clase igual, y aquí falla.
        """
        who = _user('acl.vista.lectura@kaupamex.mx')
        assert IrModelAccess.check(
            'ir.ui.view', 'read', raise_exception=False, user=who) is False


class TestDjangoCheckHook:
    """El OTRO ``check`` — el hook de *system checks* de Django.

    ``Model.check(**kwargs)`` es un classmethod que ``manage.py check`` llama
    con ``databases=…`` y del que espera una lista de mensajes. La resolución
    de permiso de la fuente se llama igual, y este modelo hereda las dos.

    Sin estos dos casos, la colisión se detecta sólo de rebote —lo hizo
    ``test_checks_irresolvable_fk``, que mide otra cosa— y un refactor que
    quitara el despacho volvería a romper ``manage.py check`` en silencio hasta
    que alguien corriera esa otra suite. Ver :ref:`h-api-840`.
    """

    def test_calling_it_without_a_model_runs_the_django_hook(self):
        """Qué lo haría fallar: quitar el despacho por firma."""
        assert IrModelAccess.check(databases=None) == []

    def test_calling_it_with_a_model_still_resolves_permission(self, db):
        """CONTROL — el despacho no puede tragarse el camino de la fuente."""
        who = _user('acl.hook.permiso@kaupamex.mx')
        assert IrModelAccess.check(
            MODEL_LABEL, 'read', raise_exception=False, user=who) is False
