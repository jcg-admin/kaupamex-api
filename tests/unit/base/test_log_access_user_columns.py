"""Las columnas de usuario del log-access: ``create_uid`` y ``write_uid``.

≙ ``odoo19c: odoo/orm/models.py:283-292`` (el metaclase añade las cuatro
columnas a todo modelo con ``_log_access``) y ``:4801-4805`` (``_create``
fija ``create_uid``/``write_uid`` con ``env.uid``). Diseño en
``designs/log-access-columns-audit.md`` del Workbench.

*Métrica:* valor de las dos columnas tras un alta y una escritura, con
usuario en contexto y sin él.
*Ciega a:* ``QuerySet.update()``, que no pasa por ``save()``. La fuente
tampoco fija nada fuera de ``create``/``write``, pero el camino aquí es
otro (``designs/log-access-columns-audit.md``, «Lo que no cierra»).
"""
import pytest

from addons.base.models import ResUsers
from addons.base.models.res_partner import ResPartnerCategory
from addons.test_orm.models.test_orm import TestOrmCategory
from orm.environments import env, sudo, user_scope
from orm.model_classes import LOG_ACCESS_COLUMNS
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


def _other_user(user):
    return ResUsers.objects.create_user(login=f'{user.login}-other',
                                        password='OtherPass123!',
                                        name='Other User')


def test_log_access_names_the_four_columns_of_the_source():
    names = {field.name for field in ResPartnerCategory._meta.fields}
    assert len(LOG_ACCESS_COLUMNS) == 4
    assert set(LOG_ACCESS_COLUMNS) <= names
    assert {'create_uid', 'write_uid'} <= set(LOG_ACCESS_COLUMNS)


def test_creation_stamps_both_users_with_the_acting_user(user):
    with user_scope(user.pk):
        tag = ResPartnerCategory.objects.create(name='Mayoristas')
    tag.refresh_from_db()
    assert tag.create_uid_id == user.pk
    assert tag.write_uid_id == user.pk


def test_a_later_write_moves_write_uid_and_keeps_create_uid(user):
    with user_scope(user.pk):
        tag = ResPartnerCategory.objects.create(name='Mayoristas')
    other = _other_user(user)
    with user_scope(other.pk):
        tag.name = 'Minoristas'
        tag.save()
    tag.refresh_from_db()
    assert tag.create_uid_id == user.pk
    assert tag.write_uid_id == other.pk


def test_without_an_acting_user_both_stay_empty():
    with user_scope(None):
        tag = ResPartnerCategory.objects.create(name='Sin usuario')
    tag.refresh_from_db()
    assert tag.create_uid_id is None
    assert tag.write_uid_id is None


def test_orm_create_and_write_stamp_through_the_contract_path(user):
    """``create``/``write`` del ORM, no ``save()``: ``write`` guarda con
    ``update_fields`` y la columna de usuario tiene que viajar con la fecha
    (``odoo19c: odoo/orm/models.py:4394-4396``)."""
    with user_scope(user.pk), sudo():
        tag = TestOrmCategory.create({'name': 'Mayoristas'})
    other = _other_user(user)
    with user_scope(other.pk), sudo():
        tag.write({'name': 'Minoristas'})
    tag.refresh_from_db()
    assert tag.create_uid_id == user.pk
    assert tag.write_uid_id == other.pk


def test_create_and_write_discard_explicit_log_access_values(user):
    """Un consumidor no fija las columnas de acceso: ``create`` y ``write``
    las descartan de ``vals`` (``odoo19c: odoo/orm/models.py:4386-4393,
    4782-4785``). ``sudo`` eleva el permiso y no cambia el usuario, como
    allá."""
    other = _other_user(user)
    with user_scope(user.pk), sudo():
        tag = TestOrmCategory.create({'name': 'Mayoristas',
                                      'create_uid': other.pk,
                                      'write_uid': other.pk})
        tag.write({'name': 'Minoristas', 'write_uid': other.pk,
                   'create_uid': other.pk})
    tag.refresh_from_db()
    assert tag.create_uid_id == user.pk
    assert tag.write_uid_id == user.pk


def test_low_level_write_stamps_the_writer(user):
    """``_write`` (``_write_multi``, el volcado de ``_flush``) también fecha
    y firma: ``log_vals | vals``
    (``odoo19c: odoo/orm/models.py:4534-4537``)."""
    with user_scope(user.pk), sudo():
        tag = TestOrmCategory.create({'name': 'Mayoristas'})
    other = _other_user(user)
    with user_scope(other.pk), sudo():
        tag._write({'name': 'Minoristas'})
    tag.refresh_from_db()
    assert tag.name == 'Minoristas'
    assert tag.write_uid_id == other.pk
    assert tag.create_uid_id == user.pk


@pytest.fixture
def loading_registry(monkeypatch):
    """La ventana de carga: el registro de la base aún no está listo."""
    registry = env().registry
    monkeypatch.setattr(registry, 'ready', False)
    return registry


def test_the_superuser_loading_data_keeps_explicit_values(user,
                                                          loading_registry):
    """``SUPERUSER_ID`` con el registro sin ``ready`` fija las columnas a
    mano; el ORM sólo rellena lo que no viene (``odoo19c:
    odoo/orm/models.py:4389,4783`` y el ``setdefault`` de ``:4395,4802``)."""
    other = _other_user(user)
    with user_scope(SUPERUSER_ID), sudo():
        tag = TestOrmCategory.create({'name': 'Semilla',
                                      'create_uid': other.pk})
        tag.write({'name': 'Semilla 2', 'write_uid': user.pk})
    tag.refresh_from_db()
    assert tag.create_uid_id == other.pk
    assert tag.write_uid_id == user.pk


def test_outside_the_loading_window_the_superuser_is_discarded(user):
    """Con el registro listo, ni el superusuario fija las columnas."""
    other = _other_user(user)
    with user_scope(SUPERUSER_ID), sudo():
        tag = TestOrmCategory.create({'name': 'Lista',
                                      'create_uid': other.pk})
    tag.refresh_from_db()
    assert tag.create_uid_id == SUPERUSER_ID
