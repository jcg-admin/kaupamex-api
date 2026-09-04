"""``UsersMultiCompany`` — la pertenencia al grupo se deriva del conteo.

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3), clase
``UsersMultiCompany``. Sus tres símbolos (``create``, ``write``, ``new``) son
**el mismo cuerpo colgado de tres ganchos**: un usuario con más de una empresa
pertenece a ``base.group_multi_company``; con una o ninguna, no.

Por qué aquí es un gancho y no tres
------------------------------------

Los tres de la fuente existen porque su ORM escribe el M2M **dentro** de
``create`` y de ``write`` —de ahí el ``if 'company_ids' not in vals: return``
de su ``write``— y porque ``new`` construye un recordset en memoria que su
cliente usa antes de guardar.

En Django un M2M **nunca** se escribe en el ``save()``: se escribe siempre por
su propio camino, y ese camino emite ``m2m_changed``. Así que la señal cubre
las dos primeras por construcción, y la tercera no tiene contraparte — no hay
recordset en memoria que sincronizar.

El control que puede fallar
---------------------------

Anulando el receptor —``return`` al entrar— la suite pasa de **8 passed** a
**5 failed, 3 passed**. Caen exactamente los cinco que afirman que la
pertenencia **cambia**: la segunda empresa la concede, volver a una la retira,
el lado inverso cuenta igual, y los dos ``clear()`` (uno por lado). Sobreviven
los tres que miden ramas negativas —sin empresa, con una sola, y un cambio de
grupos ajeno al conteo—, y sobreviven porque un receptor muerto tampoco
concede: miden otra cosa a propósito.

Sin ese control, un verde no distinguiría «la pertenencia se deriva» de «el
test no pregunta» — el sub-patrón D de ``metrica-decide-la-conclusion.md``.

*Métrica:* casos que caen al anular el receptor, sobre los 8 del archivo.
*Ciega a:* una escritura del M2M por SQL crudo o por
``ResCompanyUsersRel.objects.create()``, que no pasan por el descriptor y no
emiten la señal. La fuente tiene el mismo hueco con su ``cr.execute``.
"""

import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

MULTI = 'base.group_multi_company'


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    return ResUsers.objects.create(login=login, partner=partner)


def _make_company(name):
    return ResCompany.objects.create(name=name)


def _pertenece(user):
    return user.group_ids.filter(pk=IrModelData.ref(MULTI).pk).exists()


def test_a_user_without_companies_does_not_belong(db):
    user = _make_user('sin-empresa@ejemplo.mx')
    assert _pertenece(user) is False


def test_one_company_does_not_grant_the_group(db):
    user = _make_user('una@ejemplo.mx')
    _make_company('Alfa').user_ids.add(user)
    assert _pertenece(user) is False


def test_the_second_company_grants_the_group(db):
    user = _make_user('dos@ejemplo.mx')
    _make_company('Alfa').user_ids.add(user)
    _make_company('Beta').user_ids.add(user)
    assert _pertenece(user) is True


def test_dropping_back_to_one_revokes_the_group(db):
    user = _make_user('vuelve@ejemplo.mx')
    alfa, beta = _make_company('Alfa'), _make_company('Beta')
    alfa.user_ids.add(user)
    beta.user_ids.add(user)
    assert _pertenece(user) is True
    beta.user_ids.remove(user)
    assert _pertenece(user) is False


def test_the_reverse_side_counts_the_same(db):
    """El M2M se escribe desde los dos lados; la señal reporta ambos."""
    user = _make_user('reverso@ejemplo.mx')
    user.company_ids.set([_make_company('Alfa'), _make_company('Beta')])
    assert _pertenece(user) is True


# --- lo que NO debe tocar ---------------------------------------------------

def test_another_group_change_leaves_the_membership_alone(db):
    user = _make_user('otro-grupo@ejemplo.mx')
    _make_company('Alfa').user_ids.add(user)
    user.group_ids.add(ResGroups.objects.create(name='Contabilidad'))
    assert _pertenece(user) is False


def test_clearing_the_companies_revokes_the_group(db):
    user = _make_user('limpia@ejemplo.mx')
    user.company_ids.set([_make_company('Alfa'), _make_company('Beta')])
    assert _pertenece(user) is True
    user.company_ids.clear()
    assert _pertenece(user) is False


def test_clearing_from_the_company_side_also_revokes(db):
    """El ``clear()`` del lado de la empresa llega con ``pk_set = None``.

    Django no dice a quién vació, así que la membresía se anota en
    ``pre_clear`` y se recalcula en ``post_clear``. Es MÁS completo que la
    fuente: su ``write`` de ``res.users`` no ve una escritura hecha del lado
    de ``res.company``.
    """
    user = _make_user('desde-la-empresa@ejemplo.mx')
    alfa, beta = _make_company('Alfa'), _make_company('Beta')
    alfa.user_ids.add(user)
    beta.user_ids.add(user)
    assert _pertenece(user) is True
    beta.user_ids.clear()
    assert _pertenece(user) is False
