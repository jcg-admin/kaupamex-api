"""Los tres asistentes de credencial de ``res_users.py``.

Porta ``odoo19c: odoo/addons/base/models/res_users.py:1615-1732`` (LGPL-3):
``res.users.identitycheck``, ``change.password.wizard`` y
``change.password.user``. Antes de este pase las tres estaban **ausentes y sin
declarar** — no eran divergencia, eran hueco.

Se portan con el precedente que el arbol ya fijo en ``base_partner_merge.py``
(*"formulario, no tabla"*): los campos del wizard son parametros, y lo que es
contenedor de datos se queda como ``dataclass`` congelada.

Los tres controles que pueden fallar
-------------------------------------

1. **La linea vacia se salta, no aborta.** La fuente escribe
   ``if line.new_passwd``. Quitando esa guarda, ``_change_password`` recibe
   cadena vacia y levanta ``UserError``: cae
   ``test_a_line_without_a_password_is_skipped``, y con el la operacion
   entera, que es justo lo que la guarda evita.
2. **El aviso de auto-cambio.** Sin la comparacion ``actor.pk == user.pk`` el
   segundo elemento del retorno es siempre ``False`` y cae
   ``test_changing_your_own_password_says_so`` — el cliente no sabria que su
   sesion quedo invalida.
3. **La credencial incorrecta es ``UserError``, no ``AccessDenied``.** La
   fuente traduce a proposito, para que el dialogo muestre un mensaje legible
   en vez del error crudo del motor. Sin el ``except``, el caso ve
   ``AccessDenied`` y cae.

Medido: con las tres guardas anuladas a la vez, la suite pasa de **11 passed**
a **3 failed, 8 passed**, y caen exactamente esos tres.
"""
import pytest

from addons.base.models import ResPartner, ResUsers
from addons.base.models.res_users import (IdentityCheck, PasswordChangeLine,
                                          PasswordChangeWizard)
from exceptions import UserError
from orm.environments import user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = 'una-clave-larga-y-valida-2026'


def _make_user(login):
    partner = ResPartner.objects.create(name=login)
    user = ResUsers.objects.create(login=login, partner=partner)
    user.set_password(PASSWORD)
    user.save(update_fields=['password'])
    return user


@pytest.fixture
def admin(db):
    return _make_user('admin-de-prueba')


@pytest.fixture
def targets(db):
    return [_make_user('empleado-uno'), _make_user('empleado-dos')]


# --------------------------------------------------------------------------
# change.password.user — la linea, ≙ :1699-1712
# --------------------------------------------------------------------------

def test_the_line_captures_the_login_it_was_shown_with(targets):
    """≙ ``user_login`` readonly (``:1702``).

    La fuente lo declara aunque sea derivable, porque el operador confirma
    **contra el login que vio**, y ese login pudo cambiar desde entonces.
    """
    lines = PasswordChangeWizard.lines_for(targets, ['a', 'b'])
    assert [l.user_login for l in lines] == ['empleado-uno', 'empleado-dos']


def test_the_line_is_immutable(targets):
    """No es adorno: la fuente borra las contrasenas temporales tras usarlas.

    Aqui la linea nunca toca la base y no se puede reescribir, asi que la
    equivalencia de ese borrado es estructural en vez de un ``write``.
    """
    line = PasswordChangeWizard.lines_for(targets[:1], ['x'])[0]
    with pytest.raises(Exception):
        line.new_password = 'otra'


# --------------------------------------------------------------------------
# change.password.wizard — el bucle, ≙ :1689-1697 y :1714-1719
# --------------------------------------------------------------------------

def test_it_changes_every_password(admin, targets):
    with user_scope(admin.pk):
        changed, _ = PasswordChangeWizard.apply(
            PasswordChangeWizard.lines_for(targets, ['nueva-uno-2026',
                                                     'nueva-dos-2026']))
    assert changed == 2
    for user, nueva in zip(targets, ['nueva-uno-2026', 'nueva-dos-2026']):
        user.refresh_from_db()
        assert user.check_password(nueva)


def test_a_line_without_a_password_is_skipped(admin, targets):
    """≙ ``if line.new_passwd`` (``:1716``).

    Un campo vacio en un dialogo de N usuarios dice *"a este no"*, no
    *"aborta todo"*. Sin la guarda, ``_change_password`` levanta ``UserError``
    y se lleva por delante a los demas.
    """
    with user_scope(admin.pk):
        changed, _ = PasswordChangeWizard.apply(
            PasswordChangeWizard.lines_for(targets, ['', 'nueva-dos-2026']))
    assert changed == 1
    targets[0].refresh_from_db()
    assert targets[0].check_password(PASSWORD)      # intacta


def test_changing_your_own_password_says_so(admin, targets):
    """≙ ``if self.env.user in self.user_ids.user_id`` (``:1691``).

    La fuente devuelve un ``reload`` porque su sesion acaba de quedar
    invalida. Aqui es un dato y el cliente decide.
    """
    with user_scope(admin.pk):
        _, self_changed = PasswordChangeWizard.apply(
            PasswordChangeWizard.lines_for([admin], ['mi-nueva-clave-2026']))
    assert self_changed is True


def test_changing_someone_elses_does_not(admin, targets):
    with user_scope(admin.pk):
        _, self_changed = PasswordChangeWizard.apply(
            PasswordChangeWizard.lines_for(targets[:1], ['otra-clave-2026']))
    assert self_changed is False


def test_apply_returns_a_count_not_the_passwords(admin, targets):
    """≙ *"don't keep temporary passwords longer than necessary"* (``:1718``)."""
    with user_scope(admin.pk):
        resultado = PasswordChangeWizard.apply(
            PasswordChangeWizard.lines_for(targets[:1], ['clave-nueva-2026']))
    assert resultado == (1, False)
    assert 'clave-nueva-2026' not in repr(resultado)


# --------------------------------------------------------------------------
# res.users.identitycheck — ≙ :1615-1673
# --------------------------------------------------------------------------

def test_the_right_password_passes(admin):
    assert IdentityCheck.check_identity(admin, PASSWORD) is None


def test_the_wrong_password_raises_a_readable_error(admin):
    """≙ ``except AccessDenied: raise UserError(...)`` (``:1643-1644``).

    La fuente traduce a proposito: el dialogo muestra un mensaje al usuario,
    no el error crudo del motor.
    """
    with pytest.raises(UserError) as exc:
        IdentityCheck.check_identity(admin, 'una-clave-que-no-es')
    assert 'incorrecta' in str(exc.value).lower()


def test_the_default_auth_method_is_password(db):
    """≙ ``_get_default_auth_method`` (``:1632-1633``)."""
    assert IdentityCheck.default_auth_method() == 'password'
    assert IdentityCheck.AUTH_METHODS == (('password', 'Contraseña'),)


def test_there_is_no_generic_dispatcher():
    """``run_check`` NO se porta, y este caso lo fija.

    Deserializaba ``(ctx, model, ids, method, args, kwargs)`` y despachaba por
    ``getattr``. Portarlo seria construir un ejecutor de metodos arbitrarios
    por nombre — lo mismo que ``IrActionsServer.run()`` rehusa hacer. Si
    alguien lo anade, este caso cae y le obliga a justificarlo.
    """
    assert not hasattr(IdentityCheck, 'run_check')
