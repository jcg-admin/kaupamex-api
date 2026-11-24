"""Los cinco modelos de ``account.report*`` sobre ``BaseModel``.

≙ ``odoo19c: addons/account/models/account_report.py:44-47, 349-352,
579-582, 932-935, 947-951``: la identidad de cada clase, las relaciones
internas como recordset y la herencia de opciones de una sección.
"""
import pytest

from addons.account.models import (
    AccountReport, AccountReportColumn, AccountReportExpression,
    AccountReportExternalValue, AccountReportLine)
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

REPORT_MODELS = (AccountReport, AccountReportLine, AccountReportExpression,
                 AccountReportColumn, AccountReportExternalValue)


@pytest.mark.parametrize('model', REPORT_MODELS, ids=lambda m: m._name)
def test_each_report_model_is_a_basemodel(model):
    assert issubclass(model, BaseModel)


def test_the_external_value_checks_its_company():
    assert AccountReportExternalValue._check_company_auto is True


def test_the_lines_of_a_report_are_a_recordset():
    report = AccountReport.objects.create(name='Balance U4')
    parent = AccountReportLine.objects.create(name='Activo', report=report)
    child = AccountReportLine.objects.create(
        name='Circulante', report=report, parent=parent)
    report = AccountReport.objects.get(pk=report.pk)
    assert isinstance(report.lines, BaseModel)
    assert set(report.lines.ids) == {parent.id, child.id}
    assert child in AccountReportLine.objects.get(pk=parent.pk).children


def test_a_section_inherits_the_option_of_its_main_report():
    section = AccountReport.objects.create(
        name='Sección U4', filter_show_draft=False)
    main = AccountReport.objects.create(
        name='Principal U4', filter_show_draft=True)
    main.write({'section_reports': [(4, section.id)]})
    section = AccountReport.objects.get(pk=section.pk)
    assert section.resolver_opcion('filter_show_draft') is True
