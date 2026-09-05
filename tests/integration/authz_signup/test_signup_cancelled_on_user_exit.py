"""Tests — el signup pendiente se cancela cuando el usuario deja de usarlo.

Contrato adaptado de ``odoo19c: auth_signup/models/res_users.py`` — ``write``
(``:282-285``, al desactivar) y ``_ondelete_signup_cancel`` (``:287-292``, al
borrar). La fuente los declara como dos métodos porque su ORM separa escritura
de borrado; aquí son dos señales sobre el modelo de usuario, con el mismo
cuerpo, porque el evento que importa es el mismo.

Un ``SignupRequest`` vivo es un permiso: dice que ese partner tiene un alta o
un reset en curso. Dejarlo tras retirar al usuario deja el permiso en pie.

Los controles que exige el sub-patrón D de ``metrica-decide-la-conclusion.md``:

``test_deactivating_a_user_cancels_the_pending_signup``
    Control positivo del primer gancho. Qué lo haría fallar: retirar
    ``cancel_signup_on_deactivation``.

``test_deleting_a_user_cancels_the_pending_signup``
    Control positivo del segundo. Qué lo haría fallar: retirar
    ``cancel_signup_on_deletion``. Ningún otro caso lo mide — el de arriba
    desactiva, no borra.

``test_an_ordinary_save_does_not_cancel_anything``
    El que separa «desactivar» de «guardar». Qué lo haría fallar: mirar
    ``instance.active`` sin consultar la fila previa. Sin ese control, un
    ``save()`` cualquiera sobre un usuario **ya inactivo** cancelaría de
    nuevo, y el gancho dejaría de significar «se desactivó» para significar
    «se guardó».

**Lo que estos casos NO miden**, y se declara en vez de fabricarse: la guarda
``if user.partner_id`` de la señal. ``ResUsers.partner`` es **requerido**
—``src/addons/base/models/res_users.py:607-613``, con su razón escrita:
*"Requerido: en la referencia no hay usuario sin partner"*— así que un usuario
sin partner no se puede construir y la guarda no tiene control positivo. Se
conserva porque la fuente la escribe igual (``:291``) y porque una instancia
sin guardar sí puede llegar con ``partner_id`` en ``None``; pero eso es una
conjetura sobre el llamador, no un caso medido.

``test_a_rolled_back_deletion_keeps_the_signup``
    Qué mide: que la cancelación viaja en la transacción del borrado. Qué lo
    haría fallar: cancelar **fuera** de ella — por ejemplo en un
    ``on_commit``, o con su propia conexión.

    **Lo que NO discrimina, medido:** ``post_delete`` frente a ``pre_delete``.
    Sustituyendo uno por otro los cuatro casos siguen verdes, porque las dos
    señales corren dentro de la misma transacción y el rollback revierte las
    dos por igual. Una versión anterior de este docstring afirmaba que este
    caso separaba las dos señales; era falso. La elección de ``post_delete``
    se sostiene por la fuente —que cancela **al** borrar— y no por este test.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from addons.authz_signup.data import seed as seed_signup
from addons.authz_signup.models import res_partner as pp
from addons.authz_signup.models.signup_request import SignupRequest
from addons.base.models.res_partner import ResPartner

User = get_user_model()

pytestmark = pytest.mark.integration

PASSWORD = 'SalidaDeUsuario123!'


def _invited(login, name):
    """Un partner con signup pendiente y su usuario."""
    partner = ResPartner.objects.create(name=name, email=login)
    pp.signup_prepare(partner)
    user = User.objects.create_user(
        login=login, password=PASSWORD, partner=partner)
    return partner, user


def _pending(partner):
    return SignupRequest.objects.filter(partner=partner).exists()


@pytest.fixture
def seeded(db):
    seed_signup()


def test_deactivating_a_user_cancels_the_pending_signup(seeded):
    partner, user = _invited('desactivada@kaupamex.mx', 'Desactivada')
    assert _pending(partner), 'el alta no dejó signup pendiente'

    user.active = False
    user.save(update_fields=['active'])

    assert not _pending(partner)


def test_deleting_a_user_cancels_the_pending_signup(seeded):
    partner, user = _invited('borrada@kaupamex.mx', 'Borrada')
    assert _pending(partner)

    user.delete()

    assert not _pending(partner)


def test_an_ordinary_save_does_not_cancel_anything(seeded):
    partner, user = _invited('guardada@kaupamex.mx', 'Guardada')
    user.active = False
    user.save(update_fields=['active'])
    # Se vuelve a preparar el signup con el usuario YA inactivo: un save
    # posterior no debe volver a cancelarlo.
    pp.signup_prepare(partner)
    assert _pending(partner)

    user.save(update_fields=['active'])

    assert _pending(partner), 'un save sobre un usuario ya inactivo canceló'


def test_a_rolled_back_deletion_keeps_the_signup(seeded):
    partner, user = _invited('revertida@kaupamex.mx', 'Revertida')

    class _Abortar(Exception):
        pass

    with pytest.raises(_Abortar):
        with transaction.atomic():
            user.delete()
            raise _Abortar

    assert _pending(partner), \
        'la cancelación sobrevivió al rollback del borrado que la motivó'
