"""Tests — el resolvedor compuesto: ACL primero, reglas de registro después.

≙ ``odoo19c: odoo/orm/models.py:4135`` (``_check_access``) y sus tres formas
públicas: ``check_access`` (levanta), ``has_access`` (booleano) y
``_filtered_access`` (filtra).

Lo que la fuente compone, y en ese orden
=========================================

``_check_access`` pregunta **dos** cosas y la primera manda:

1. ``ir.model.access.check(model, operation)`` — ¿puede este usuario la
   operación sobre el **modelo**? Si no, los registros prohibidos son *todos*.
2. Sólo si pasó: ``ir.rule._compute_domain(model, operation)`` — ¿qué **filas**
   le deja ver? Los prohibidos son los que el dominio no devuelve.

El orden importa y es medible: sin permiso de modelo, la fuente **ni evalúa las
reglas**. Un resolvedor que las evaluara igual devolvería "0 filas prohibidas"
para un modelo cuya ACL deniega entero — verde por la vía equivocada.

Qué haría fallar a cada control
--------------------------------

``TestComposedResolver.test_without_model_permission_every_row_is_forbidden``
    El eje: la primera mitad manda sobre la segunda.

``TestComposedResolver.test_with_model_permission_the_rules_still_narrow``
    CONTROL de que la segunda mitad existe. Sin él, un resolvedor que sólo
    consultara la ACL pasaría todo lo demás.

``TestForms.test_under_su_the_three_forms_allow_everything``
    CONTROL del bypass, en las tres formas a la vez.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models import ResCompany
from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups
from exceptions import AccessError
from orm.environments import sudo
from orm.models import AccessQuerySet

pytestmark = pytest.mark.integration

MODEL_LABEL = 'base.ResCompany'
CODES = ('acqs-alfa', 'acqs-beta', 'acqs-gama')


@pytest.fixture
def three_companies(db):
    for code in CODES:
        ResCompany.objects.create(code=code, name=code.title())


def _rows():
    """El queryset acotado a las tres del fixture, con las cuatro formas."""
    return AccessQuerySet(model=ResCompany).filter(code__in=CODES)


def _grant(mode='read', group=None):
    row, _ = IrModel.objects.get_or_create(
        model=MODEL_LABEL, defaults={'name': 'Compañía'})
    return IrModelAccess.objects.create(
        name=f'acqs {mode} {group.pk if group else "global"}',
        model_id=row, group_id=group, **{f'perm_{mode}': True})


def _user(login):
    return get_user_model().objects.create_user(
        login=login, password='AcqsPrueba123!')


class TestComposedResolver:
    """≙ ``_check_access`` — el par ``(prohibidos, fábrica de error)``."""

    def test_without_model_permission_every_row_is_forbidden(
            self, three_companies):
        who = _user('acqs.sin.modelo@practicayoruba.mx')
        forbidden, make_error = _rows()._check_access('read', user=who)
        assert forbidden.count() == 3, 'sin permiso de modelo, todas'
        assert isinstance(make_error(), AccessError)

    def test_with_model_permission_and_no_rule_nothing_is_forbidden(
            self, three_companies):
        _grant('read')
        who = _user('acqs.con.modelo@practicayoruba.mx')
        assert _rows()._check_access('read', user=who) is None

    def test_with_model_permission_the_rules_still_narrow(
            self, three_companies):
        """CONTROL — sin esto, consultar sólo la ACL pasaría igual."""
        _grant('read')
        IrRule.objects.create(
            name='acqs sólo alfa', model_name=MODEL_LABEL,
            domain_force="[('code', '=', 'acqs-alfa')]")
        who = _user('acqs.regla@practicayoruba.mx')
        forbidden, _ = _rows()._check_access('read', user=who)
        assert set(forbidden.values_list('code', flat=True)) == {
            'acqs-beta', 'acqs-gama'}

    def test_the_rules_are_not_evaluated_without_model_permission(
            self, three_companies):
        """El orden es observable: la regla dejaría pasar una, la ACL ninguna."""
        IrRule.objects.create(
            name='acqs sólo alfa (sin acl)', model_name=MODEL_LABEL,
            domain_force="[('code', '=', 'acqs-alfa')]")
        who = _user('acqs.orden@practicayoruba.mx')
        forbidden, _ = _rows()._check_access('read', user=who)
        assert forbidden.count() == 3


class TestForms:
    """Las tres formas públicas — ``check_access``/``has_access``/filtrado."""

    def test_has_access_is_false_without_model_permission(
            self, three_companies):
        who = _user('acqs.has.no@practicayoruba.mx')
        assert _rows().has_access('read', user=who) is False

    def test_has_access_is_true_with_it(self, three_companies):
        _grant('read')
        who = _user('acqs.has.si@practicayoruba.mx')
        assert _rows().has_access('read', user=who) is True

    def test_check_access_raises_and_names_the_model(self, three_companies):
        who = _user('acqs.check@practicayoruba.mx')
        with pytest.raises(AccessError) as caught:
            _rows().check_access('write', user=who)
        assert MODEL_LABEL in str(caught.value)

    def test_check_access_is_silent_when_allowed(self, three_companies):
        _grant('write')
        who = _user('acqs.check.ok@practicayoruba.mx')
        assert _rows().check_access('write', user=who) is None

    def test_filtered_access_returns_the_subset_the_rules_allow(
            self, three_companies):
        _grant('read')
        IrRule.objects.create(
            name='acqs filtra a beta', model_name=MODEL_LABEL,
            domain_force="[('code', '=', 'acqs-beta')]")
        who = _user('acqs.filtra@practicayoruba.mx')
        allowed = _rows()._filtered_access('read', user=who)
        assert set(allowed.values_list('code', flat=True)) == {'acqs-beta'}

    def test_filtered_access_returns_nothing_without_model_permission(
            self, three_companies):
        who = _user('acqs.filtra.no@practicayoruba.mx')
        assert _rows()._filtered_access('read', user=who).count() == 0

    def test_under_su_the_three_forms_allow_everything(self, three_companies):
        """CONTROL del bypass — la fuente ni consulta bajo ``su``."""
        IrRule.objects.create(
            name='acqs nada pasa', model_name=MODEL_LABEL,
            domain_force="[('code', '=', 'no-existe')]")
        who = _user('acqs.su@practicayoruba.mx')
        with sudo():
            assert _rows().has_access('read', user=who) is True
            assert _rows().check_access('read', user=who) is None
            assert _rows()._filtered_access('read', user=who).count() == 3

    def test_a_group_acl_opens_it_to_its_members(self, three_companies):
        group = ResGroups.objects.create(name='lectores de compañía',
                                         user_type='internal')
        _grant('read', group=group)
        who = _user('acqs.grupo@practicayoruba.mx')
        assert _rows().has_access('read', user=who) is False, 'sin el grupo, no'
        who.group_ids.add(group)
        assert _rows().has_access('read', user=who) is True
