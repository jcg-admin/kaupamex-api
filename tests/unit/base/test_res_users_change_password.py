"""``change_password`` / ``_change_password`` — cambiar la propia contraseña.

Porta el contrato de ``odoo19c: odoo/addons/base/models/res_users.py:899-932``.
La fuente separa dos eslabones a proposito:

- ``change_password(old, new)`` es la puerta **autoportante**: exige la
  contraseña anterior, que es ella misma la prueba de identidad. Su docstring
  dice por que — *"to prevent hijacking an existing user session"*.
- ``_change_password(new)`` es el interno: no verifica identidad, recorta,
  rechaza el vacio y deja el rastro de quien cambio la de quien.

El control que puede fallar
---------------------------

Medido anulando la verificacion de la anterior —sustituyendo el cuerpo de
``change_password`` por una llamada directa a ``_change_password``— el
subconjunto pasa de **11 passed** a **2 failed, 9 passed**. Caen exactamente
los dos que afirman que la anterior **se exige y se comprueba**:

- ``test_the_old_password_is_required``
- ``test_a_wrong_old_password_is_refused``

Sobreviven nueve, y hay uno que conviene mirar de frente:
``test_the_right_old_password_changes_it`` **pasa igual sin la guarda**, porque
con la contraseña correcta el desenlace es el mismo la haya comprobado alguien
o no. No es un caso defectuoso —mide el camino feliz, que hay que medir— pero
por si solo no es una red. Los otros ocho miden el eslabon interno, que por
diseño no verifica identidad.

Prediccion contra medicion: antes de correrlo se escribio aqui «tres caen, ocho
sobreviven». La cifra real es 2/9, y el que sobro es justo el del camino feliz.
Ver ``metrica-decide-la-conclusion.md`` sub-patron D.
"""
import logging

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from addons.base.models.ir_http import set_current_request
from exceptions import AccessDenied, UserError

CURRENT = 'contrasena-actual-9F'
NEW = 'contrasena-nueva-4K'


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        login='ana.tester', password=CURRENT)


@pytest.fixture
def request_context():
    def _set(ip='203.0.113.7'):
        set_current_request(RequestFactory().get('/', REMOTE_ADDR=ip))
    yield _set
    set_current_request(None)


# --------------------------------------------------------------------------
# change_password — la puerta, y lo que exige
# --------------------------------------------------------------------------

def test_the_old_password_is_required(user):
    """Sin la anterior no se abre, aunque haya sesion viva."""
    with pytest.raises(AccessDenied):
        user.change_password('', NEW)
    user.refresh_from_db()
    assert user.check_password(CURRENT) is True


def test_a_wrong_old_password_is_refused(user):
    with pytest.raises(AccessDenied):
        user.change_password('la-que-no-es', NEW)
    user.refresh_from_db()
    assert user.check_password(CURRENT) is True


def test_the_right_old_password_changes_it(user):
    assert user.change_password(CURRENT, NEW) is True
    user.refresh_from_db()
    assert user.check_password(NEW) is True
    assert user.check_password(CURRENT) is False


def test_an_empty_new_password_is_refused(user):
    """El vacio lo rechaza el eslabon interno, ya pasada la identidad."""
    with pytest.raises(UserError):
        user.change_password(CURRENT, '')
    user.refresh_from_db()
    assert user.check_password(CURRENT) is True


# --------------------------------------------------------------------------
# _change_password — el interno
# --------------------------------------------------------------------------

def test_it_does_not_check_identity(user):
    """Por diseño: quien llama ya la verifico. La fuente lo separa asi."""
    user._change_password(NEW)
    user.refresh_from_db()
    assert user.check_password(NEW) is True


def test_it_strips_the_new_password(user):
    user._change_password(f'  {NEW}  ')
    user.refresh_from_db()
    assert user.check_password(NEW) is True


def test_whitespace_only_counts_as_empty(user):
    with pytest.raises(UserError):
        user._change_password('     ')
    user.refresh_from_db()
    assert user.check_password(CURRENT) is True


def test_none_counts_as_empty(user):
    with pytest.raises(UserError):
        user._change_password(None)


def test_it_persists(user):
    """DIVERGENCIA: la fuente escribe en la asignacion; Django necesita save."""
    user._change_password(NEW)
    fresh = get_user_model().objects.get(pk=user.pk)
    assert fresh.check_password(NEW) is True


def test_it_leaves_a_trace(user, request_context, caplog):
    """El rastro que hace auditable un cambio de credencial."""
    request_context(ip='198.51.100.9')
    with caplog.at_level(logging.INFO, logger='addons.base.models.res_users'):
        user._change_password(NEW)
    messages = [r.getMessage() for r in caplog.records]
    assert any('ana.tester' in m and '198.51.100.9' in m for m in messages)


def test_outside_a_request_the_trace_says_so(user, caplog):
    """Sin peticion no hay origen — la fuente escribe 'n/a' y aqui igual."""
    set_current_request(None)
    with caplog.at_level(logging.INFO, logger='addons.base.models.res_users'):
        user._change_password(NEW)
    assert any('n/a' in r.getMessage() for r in caplog.records)
