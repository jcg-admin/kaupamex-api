"""``res.users`` — los dos ejes de compañía de la referencia.

La referencia declara **dos** campos, no uno (``odoo-tools@622ddc2a``):

- ``company_id`` (``odoo19c: res_users.py:245``) — la compañía activa por
  defecto. Aquí es ``ResUsers.company``.
- ``company_ids`` (``odoo19c: res_users.py:247``; ``odoo18c: :403``) — el
  conjunto alcanzable **sin volver a autenticarse**. Aquí existe como
  reverso del M2M de ``ResCompany.user_ids``.

Se cubren las tres piezas que gobiernan ese par en la fuente: los nombres de
columna de la tabla de relación, el constraint ``_check_user_company``
(``:501-511``) y el filtro de compañías archivadas de ``_get_company_ids``
(``:726-730``).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models.res_company import ResCompany, ResCompanyUsersRel
from addons.base.models.res_users import ResUsers


@pytest.fixture
def companias(db):
    return (
        ResCompany.objects.create(name='Alfa'),
        ResCompany.objects.create(name='Beta'),
    )


@pytest.fixture
def usuario(db, companias):
    alfa, _ = companias
    user = ResUsers.objects.create_user(login='u@kaupamex.test', password='x')
    user.company = alfa
    user.save(update_fields=['company'])
    return user


def test_tabla_de_relacion_usa_las_columnas_de_la_referencia():
    """``cid``/``user_id``, no los ``rescompany_id``/``resusers_id`` de Django."""
    columnas = {f.column for f in ResCompanyUsersRel._meta.fields}
    assert ResCompanyUsersRel._meta.db_table == 'res_company_users_rel'
    assert {'cid', 'user_id'} <= columnas


def test_company_ids_es_el_reverso_del_m2m(usuario, companias):
    alfa, beta = companias
    usuario.company_ids.add(alfa, beta)
    assert set(usuario.company_ids.values_list('pk', flat=True)) == {alfa.pk, beta.pk}
    assert usuario in alfa.user_ids.all()


def test_constraint_rechaza_company_fuera_de_las_permitidas(usuario, companias):
    """``_check_user_company``: la compañía por defecto debe estar permitida."""
    _, beta = companias
    usuario.company_ids.add(beta)          # permitida: sólo Beta
    with pytest.raises(ValidationError) as exc:
        usuario.clean()                     # company = Alfa
    assert 'no está entre las permitidas' in str(exc.value)


def test_constraint_pasa_cuando_la_propia_esta_permitida(usuario, companias):
    alfa, beta = companias
    usuario.company_ids.add(alfa, beta)
    usuario.clean()                         # no lanza


def test_constraint_no_aplica_a_usuario_inactivo(usuario, companias):
    """La fuente filtra ``lambda u: u.active`` antes de validar."""
    _, beta = companias
    usuario.company_ids.add(beta)
    usuario.active = False
    usuario.clean()                         # no lanza


def test_permitidas_ponen_la_propia_primero(usuario, companias):
    """``env.company`` es la primera activada — de ahí el orden."""
    alfa, beta = companias
    usuario.company_ids.add(beta, alfa)
    assert usuario._permitted_company_ids()[0] == alfa.pk


def test_permitidas_excluyen_companias_archivadas(usuario, companias):
    """``_get_company_ids`` filtra ``('active', '=', True)``."""
    alfa, beta = companias
    usuario.company_ids.add(alfa, beta)
    beta.active = False
    beta.save(update_fields=['active'])
    assert usuario._permitted_company_ids() == (alfa.pk,)
