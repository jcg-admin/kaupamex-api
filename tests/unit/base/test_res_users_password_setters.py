"""``_set_encrypted_password`` y ``_set_new_password`` (``:299-306``, ``:414-426``).

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3). Son las dos
mitades del bloque de contraseña que **no** son divergencia de stack.

Qué hace cada una, y por qué sobrevive al cambio de ORM
--------------------------------------------------------

- ``_set_encrypted_password(uid, pw)`` escribe un hash **ya calculado**, y
  antes afirma que no es texto plano: ``assert self._crypt_context()
  .identify(pw) != 'plaintext'``. Es la vía por la que entra una credencial
  que se cifró en otra parte —una importación, un directorio LDAP— sin volver
  a pasarla por el cifrador. Sin ella, escribir en ``password`` un hash lo
  vuelve a hashear y la credencial deja de validar.
- ``_set_new_password`` es el *inverse* del campo ``new_password`` de su
  formulario, y lleva dentro una regla que **no** es de formulario: un usuario
  no cambia su **propia** contraseña por esta vía. Su comentario lo explica —
  *"To change their own password, users must use the client-specific change
  password wizard, so that the new password is immediately used for further
  RPC requests, otherwise the user will face unexpected 'Access Denied'
  exceptions."* Aquí la vía propia es :meth:`ResUsers.change_password`, que
  exige la anterior.

El control que puede fallar
---------------------------

Anulando la aserción de ``_set_encrypted_password`` cae el caso que le pasa
texto plano; anulando la guarda de identidad de ``_set_new_password`` cae el
que afirma que un usuario no se cambia la suya por esa vía. Los demás miden el
camino feliz y sobreviven — y está bien que lo hagan: lo que no valdría es no
saber cuáles son.

*Métrica:* casos que caen al anular cada guarda, sobre los 7 del archivo.
*Ciega a:* que el hash escrito sea el correcto para OTRO usuario — el método
recibe un ``uid`` y no comprueba a quién pertenece el hash, igual que la
fuente.
"""

import pytest

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from exceptions import UserError
from orm.environments import user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    user = ResUsers.objects.create(login=login, partner=partner)
    user.set_password('la-de-antes')
    user.save(update_fields=['password'])
    return user


# El hash de prueba se construye con ``_crypt_context()``, no con el registro
# global de Django: la guarda del metodo pregunta ``identify(pw) != 'plaintext'``
# contra ESE contexto, asi que un hash de otro cifrador es, para el, texto
# plano — y lo rechaza, que es la conducta de la fuente.

# --- _set_encrypted_password ----------------------------------------------

def test_an_already_hashed_password_is_stored_verbatim(db):
    user = _make_user('hash@ejemplo.mx')
    cifrada = ResUsers._crypt_context().hash('la-nueva')
    ResUsers._set_encrypted_password(user.pk, cifrada)
    user.refresh_from_db()
    assert user.password == cifrada


def test_the_stored_hash_still_validates_its_plaintext(db):
    user = _make_user('valida@ejemplo.mx')
    ResUsers._set_encrypted_password(user.pk, ResUsers._crypt_context().hash('la-nueva'))
    user.refresh_from_db()
    assert user.check_password('la-nueva')


def test_a_plaintext_password_is_refused(db):
    """La aserción de la fuente: por aquí no entra texto plano."""
    user = _make_user('plano@ejemplo.mx')
    with pytest.raises(UserError):
        ResUsers._set_encrypted_password(user.pk, 'la-nueva-en-claro')
    user.refresh_from_db()
    assert user.check_password('la-de-antes')


def test_only_the_named_user_is_touched(db):
    uno = _make_user('uno@ejemplo.mx')
    dos = _make_user('dos@ejemplo.mx')
    ResUsers._set_encrypted_password(uno.pk, ResUsers._crypt_context().hash('otra'))
    dos.refresh_from_db()
    assert dos.check_password('la-de-antes')


# --- _set_new_password ------------------------------------------------------

def test_an_administrator_sets_the_password_of_someone_else(db):
    actor = _make_user('admin@ejemplo.mx')
    otro = _make_user('otro@ejemplo.mx')
    with user_scope(actor.pk):
        otro._set_new_password('la-que-le-pongo')
    otro.refresh_from_db()
    assert otro.check_password('la-que-le-pongo')


def test_nobody_changes_their_own_password_through_this_path(db):
    """≙ ``:421-424`` — para la propia va ``change_password``, que pide la
    anterior; por esta vía la sesión en curso quedaría con la credencial vieja.
    """
    user = _make_user('propia@ejemplo.mx')
    with user_scope(user.pk):
        with pytest.raises(UserError):
            user._set_new_password('me-la-cambio-yo')
    user.refresh_from_db()
    assert user.check_password('la-de-antes')


def test_an_empty_value_is_ignored_in_silence(db):
    """≙ ``:416-419`` — *"Do not update the password if no value is provided,
    ignore silently"*: su cliente envía ``False`` en todo campo vacío."""
    actor = _make_user('vacio-actor@ejemplo.mx')
    otro = _make_user('vacio@ejemplo.mx')
    with user_scope(actor.pk):
        otro._set_new_password('')
    otro.refresh_from_db()
    assert otro.check_password('la-de-antes')
