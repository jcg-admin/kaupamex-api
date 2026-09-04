"""``_deactivate_portal_user`` — la baja de una cuenta de portal (``:934-987``).

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3). Su
docstring de la fuente dice para qué existe: *"This is used to give the
opportunity to portal users to de-activate their accounts […] Before this
feature, they would have to contact the website or the support to get their
account removed, which could be tedious."*

Por qué es trabajo y no divergencia
------------------------------------

El consumidor **ya existía** en este árbol y hacía una versión parcial a mano:
``addons/portal/controllers/main.py`` archivaba al usuario y encolaba la fila
de ``res.users.deletion``, y **omitía** las otras cinco mitades del método de
la fuente — la guarda de que sólo un usuario de portal puede darse de baja, la
ofuscación del *login*, la inutilización de la contraseña, el retiro de las
claves de API y el archivado del partner. Omitía además algo que la fuente no
tiene y este árbol sí: ``deactivated_reason``, sin el cual el flujo de
reactivación por email no distingue una baja voluntaria de una suspensión.

El control que puede fallar
---------------------------

Anulando la guarda de clase —``_deactivate_portal_user`` con un ``return``
antes del ``filtered``— caen los dos casos que afirman que un usuario interno
**no** puede darse de baja por esta vía. Anulando el cuerpo entero caen los
diez restantes. Ninguno de los doce pasa por accidente: cada uno lee un efecto
distinto sobre la fila.

*Métrica:* casos que caen al anular la guarda y el cuerpo, sobre los 12 del
archivo.
*Ciega a:* un efecto que el método produzca y que ningún caso lea — por
ejemplo la línea de bitácora, que se emite y no se afirma aquí.
"""

import pytest

from addons.base.models.res_users import ResUsers
from addons.base.models.res_users_deletion import ResUsersDeletion
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsersApikeys
from exceptions import AccessDenied
from orm.environments import user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_user(login, internal=False):
    partner = ResPartner.objects.create(name=login, email='')
    user = ResUsers.objects.create(login=login, partner=partner)
    user.set_password('secreto-original')
    user.save(update_fields=['password'])
    if internal:
        user.group_ids.add(
            ResGroups.objects.create(name='Empleados %s' % login,
                                     user_type=ResGroups.USER_TYPE_INTERNAL))
    return user


# --- la guarda de clase: sólo un usuario de portal se da de baja -----------

def test_an_internal_user_cannot_deactivate_its_own_account(db):
    user = _make_user('interno@ejemplo.mx', internal=True)
    with pytest.raises(AccessDenied):
        ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.refresh_from_db()
    assert user.active is True


def test_a_batch_with_one_internal_user_deactivates_nobody(db):
    portal = _make_user('portal@ejemplo.mx')
    interno = _make_user('otro-interno@ejemplo.mx', internal=True)
    with pytest.raises(AccessDenied):
        ResUsers.objects.filter(pk__in=[portal.pk, interno.pk])._deactivate_portal_user()
    portal.refresh_from_db()
    assert portal.active is True


# --- los efectos sobre la fila del usuario --------------------------------

def test_the_portal_user_is_archived(db):
    user = _make_user('baja@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.refresh_from_db()
    assert user.active is False


def test_the_reason_says_the_user_asked_for_it(db):
    user = _make_user('razon@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.refresh_from_db()
    assert user.deactivated_reason == ResUsers.DEACTIVATION_SELF_DELETED


def test_the_deactivation_is_dated(db):
    user = _make_user('fecha@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.refresh_from_db()
    assert user.deactivated_at is not None


def test_the_login_is_scrambled(db):
    user = _make_user('scramble@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.refresh_from_db()
    assert user.login != 'scramble@ejemplo.mx'
    assert user.login.startswith('__deleted_user_%s_' % user.pk)


def test_the_old_password_no_longer_validates(db):
    user = _make_user('clave@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.refresh_from_db()
    assert not user.check_password('secreto-original')


def test_the_partner_is_archived_too(db):
    user = _make_user('partner@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    user.partner.refresh_from_db()
    assert user.partner.active is False


# --- la cola de borrado ----------------------------------------------------

def test_the_user_is_queued_for_deletion(db):
    user = _make_user('cola@ejemplo.mx')
    ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    fila = ResUsersDeletion.objects.get(user_int=user.pk)
    assert fila.state == ResUsersDeletion.STATE_TODO


def test_a_batch_queues_one_row_per_user(db):
    uno = _make_user('lote-uno@ejemplo.mx')
    dos = _make_user('lote-dos@ejemplo.mx')
    ResUsers.objects.filter(pk__in=[uno.pk, dos.pk])._deactivate_portal_user()
    assert ResUsersDeletion.objects.filter(
        user_int__in=[uno.pk, dos.pk]).count() == 2


def test_the_batch_archives_both(db):
    uno = _make_user('ambos-uno@ejemplo.mx')
    dos = _make_user('ambos-dos@ejemplo.mx')
    ResUsers.objects.filter(pk__in=[uno.pk, dos.pk])._deactivate_portal_user()
    assert ResUsers.objects.filter(
        pk__in=[uno.pk, dos.pk], active=True).count() == 0


# --- las claves de API ------------------------------------------------------

def test_the_api_keys_are_removed(db):
    """Como en la fuente, ``_remove`` sigue exigiendo identidad: la baja la
    pide el propio usuario, así que el actor es él."""
    user = _make_user('llaves@ejemplo.mx')
    clave = ResUsersApikeys.objects.create(
        user=user, name='una', index='abcdefgh', key='no-importa')
    with user_scope(user.pk):
        ResUsers.objects.filter(pk=user.pk)._deactivate_portal_user()
    assert not ResUsersApikeys.objects.filter(pk=clave.pk).exists()
