"""La cabecera de ``account.analytic.line`` y de su mixin.

≙ ``odoo19c: addons/analytic/models/analytic_line.py:11-14`` y ``:163-168``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
analytic-model-headers.md``.

*Métrica:* los atributos de clase, las columnas de acceso registrado, el
XML-ID que ``account`` recibe y la fila de acceso de ``purchase``.
*Ciega a:* ``check_company=True`` en los relacionales y los nombres de FK en
forma A, que el diseño declara con su sucesor.
"""
import pytest

from addons.analytic.models import AccountAnalyticLine, AnalyticPlanFieldsMixin
from addons.base.models import IrModelData
from orm.registry import MODELS_EXTENDED_BY_MODULE

pytestmark = pytest.mark.django_db


def test_the_mixin_header_is_the_reference():
    attrs = AnalyticPlanFieldsMixin.__dict__
    assert attrs['_name'] == 'analytic.plan.fields.mixin'
    assert attrs['_description'] == 'Analytic Plan Fields'
    assert attrs['_abstract'] is True


def test_the_line_header_is_the_reference():
    attrs = AccountAnalyticLine.__dict__
    assert attrs['_name'] == 'account.analytic.line'
    assert attrs['_inherit'] == ['analytic.plan.fields.mixin']
    assert attrs['_description'] == 'Analytic Line'
    assert attrs['_order'] == 'date desc, id desc'
    assert attrs['_check_company_auto'] is True


@pytest.mark.parametrize('name', [
    'create_uid', 'create_date', 'write_uid', 'write_date'])
def test_the_line_has_its_log_access_column(name):
    assert AccountAnalyticLine._meta.get_field(name).column == name


def test_account_receives_the_model_xmlid():
    assert IrModelData.objects.filter(
        module='account', name='model_account_analytic_line',
        model='base.IrModel').exists()


def test_the_purchase_access_row_loads():
    assert IrModelData.objects.filter(
        module='purchase', name='access_account_analytic_line',
        model='base.IrModelAccess').exists()


def test_account_is_recorded_as_extending_the_line():
    """El mecanismo, no el estado de la base: con ``--reuse-db`` el XML-ID
    sobrevive de una carga anterior, y sólo esta anotación dice que
    ``account`` lo recibiría en una carga limpia."""
    assert 'account.analytic.line' in MODELS_EXTENDED_BY_MODULE['account']
