"""Las tres restricciones de integridad de ``res.users`` — ``:535-556``, ``:647-660``.

Porta ``odoo19c: odoo/addons/base/models/res_users.py`` (LGPL-3):
``_check_disjoint_groups``, ``_check_at_least_one_administrator`` y
``_unlink_except_master_data``, mas ``_check_company_domain`` y
``_get_group_ids``.

Que protege cada una, en palabras de la fuente
-----------------------------------------------

- **Clases disjuntas** (``:537-538``): *"We check that no users are both
  portal and users (same with public). This could typically happen because of
  implied groups."* Un usuario en dos clases rompe todo lo que decide por
  clase, empezando por ``share``, que es literalmente «no es interno».
- **Al menos un administrador** (``:554``): quitarle el ultimo grupo de
  sistema al ultimo administrador deja la instalacion sin quien la administre
  y sin nadie que pueda devolverlo.
- **Datos maestros** (``:648-660``): el super-usuario, el administrador y el
  usuario publico no se borran — se archivan.

El control que puede fallar
---------------------------

Anulando las tres guardas —``_check_disjoint_groups`` con ``return`` al
entrar, ``_check_at_least_one_administrator`` igual, y ``delete()`` delegando
sin comprobar— la suite pasa de **14 passed** a **7 failed, 7 passed**. Caen
los siete que afirman que la restriccion **ocurre** (dos de clases disjuntas,
uno del administrador, cuatro de datos maestros — el borrado esta
parametrizado por login). Sobreviven los siete que miden las ramas negativas
—una sola clase pasa, ninguna clase pasa, con administrador calla, sin xmlid
no aplica, un usuario normal si se borra— y los dos ayudantes, que no son
restricciones.

Lo que este archivo NO cubre, y esta declarado
-----------------------------------------------

El borrado **en lote** por ``QuerySet.delete()`` no pasa por el ``delete()``
del modelo — limitacion de Django, no del porte, declarada en el docstring
del metodo. Sucesor: tarea **#57**.
"""
import pytest

from addons.base.models import (IrModelData, ResGroups, ResPartner,
                                ResUsers)
from django.core.exceptions import ValidationError
from exceptions import UserError
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_user(login):
    partner = ResPartner.objects.create(name=login, email='')
    return ResUsers.objects.create(login=login, partner=partner)


def _make_group(name, user_type=None):
    return ResGroups.objects.create(name=name, user_type=user_type)


# --------------------------------------------------------------------------
# Clases disjuntas — ≙ :535-548
# --------------------------------------------------------------------------

def test_one_class_is_fine(db):
    """La rama negativa: un solo tipo no viola nada."""
    user = _make_user('interno-solo')
    user.group_ids.add(_make_group('Empleados', 'internal'))
    user._check_disjoint_groups()


def test_no_class_at_all_is_fine(db):
    """Un grupo sin ``user_type`` no participa del eje — no debe estorbar."""
    user = _make_user('sin-clase')
    user.group_ids.add(_make_group('Contabilidad'))
    user._check_disjoint_groups()


def test_two_classes_at_once_are_rejected(db):
    """≙ ``:543-548`` — interno y portal a la vez no es un estado valido."""
    user = _make_user('doble-clase')
    user.group_ids.add(_make_group('Empleados', 'internal'))
    user.group_ids.add(_make_group('Portal', 'portal'))
    with pytest.raises(ValidationError, match='excluyentes'):
        user._check_disjoint_groups()


def test_clean_runs_the_disjoint_check(db):
    """La restriccion entra por ``clean()``, que es su unica via aqui.

    Django no valida M2M en ``full_clean()`` porque la relacion no existe
    hasta que la fila tiene PK — la misma razon por la que
    ``_check_user_company`` se porta asi.
    """
    user = _make_user('doble-por-clean')
    user.group_ids.add(_make_group('Empleados', 'internal'))
    user.group_ids.add(_make_group('Publico', 'public'))
    with pytest.raises(ValidationError):
        user.clean()


# --------------------------------------------------------------------------
# Al menos un administrador — ≙ :550-555
# --------------------------------------------------------------------------

@pytest.fixture
def system_group(db):
    """El ``base.group_system`` que la siembra ya deja puesto.

    Se resuelve por su xmlid en vez de crearlo: el conftest lo siembra, y
    crear un segundo choca con ``ir_model_data_module_name_uniq`` — que es
    justo lo que hace de la siembra la unica fuente.
    """
    grupo = IrModelData.ref('base.group_system', raise_if_not_found=False)
    assert grupo is not None, 'la siembra debe dejar base.group_system'
    return grupo


def test_without_a_system_group_the_rule_does_not_apply(db):
    """≙ el ``if not self.env.registry._init_modules: return`` de la fuente.

    Mientras el grupo de sistema no resuelva, la pregunta no tiene sentido:
    el arbol todavia no llego al punto en que hay algo que exigir. Se retira
    su xmlid para medirlo — es el unico modo de reproducir el estado previo a
    la siembra dentro de una transaccion.
    """
    IrModelData.objects.filter(module='base', name='group_system').delete()
    ResUsers._check_at_least_one_administrator()


def test_a_system_group_with_nobody_in_it_is_rejected(system_group):
    """≙ ``:554`` — *"You must have at least an administrator user."*"""
    system_group.user_ids.clear()
    with pytest.raises(ValidationError, match='administrador'):
        ResUsers._check_at_least_one_administrator()


def test_a_system_group_with_a_member_passes(system_group):
    """La rama negativa: con administrador, la restriccion calla."""
    system_group.user_ids.clear()
    _make_user('el-admin').group_ids.add(system_group)
    ResUsers._check_at_least_one_administrator()


# --------------------------------------------------------------------------
# Datos maestros — ≙ :647-660
# --------------------------------------------------------------------------

def test_a_plain_user_can_be_deleted(db):
    """La rama negativa, y la que hace util a la guarda: sin ella no habria
    nada que distinguir."""
    user = _make_user('prescindible')
    pk = user.pk
    user.delete()
    assert not ResUsers.objects.filter(pk=pk).exists()


def test_the_superuser_cannot_be_deleted(db):
    """≙ ``:651-652`` — *"it is used internally for resources created by Odoo
    (updates, module installation, ...)"*."""
    user = _make_user('cualquier-login')
    user.pk = SUPERUSER_ID
    with pytest.raises(UserError, match='super-usuario'):
        user.delete()


@pytest.mark.parametrize('login', ['admin', 'public', '__system__'])
def test_the_system_logins_cannot_be_deleted(db, login):
    """≙ ``:654-660`` — el administrador y el usuario publico se archivan, no
    se borran. El cuarto de la fuente, la plantilla de usuario portal, no
    existe en este arbol: se invita por endpoint."""
    user = _make_user(login)
    with pytest.raises(UserError, match='Archívalo'):
        user.delete()


# --------------------------------------------------------------------------
# Los dos ayudantes — ≙ :169-173 y :1098-1104
# --------------------------------------------------------------------------

def test_an_empty_company_set_filters_nothing(db):
    """≙ ``Domain.TRUE`` (``:170-171``) — sin empresas, no hay que exigir."""
    assert ResUsers._check_company_domain(None).children == []


def test_the_group_ids_include_the_implied_ones(db):
    """≙ ``_get_group_ids`` (``:1098-1104``) — todos, implicados incluidos.

    NO se memoriza, y la razon esta declarada: sin invalidador, una cache de
    autorizacion mantendria vivo un permiso ya retirado. Sucesor: tarea #58.
    """
    user = _make_user('con-grupos')
    grupo = _make_group('Ventas')
    user.group_ids.add(grupo)
    assert grupo.pk in user._get_group_ids()
