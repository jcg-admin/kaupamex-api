"""Los formatos de papel de ``base`` y ``res.company.init``.

≙ ``odoo19c: odoo/addons/base/data/report_paperformat_data.xml``
(``noupdate="1"``) y ``res.company.init`` (``odoo19c: odoo/addons/base/
models/res_company.py:102-109``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/paperformat-company-init.md``.
"""
import pytest
from django.db import connection

from addons.base.data.report_paperformat_data import seed
from addons.base.models import IrModelData, ResCompany
from addons.base.models.report_paperformat import ReportPaperformat
from orm.registry import Registry

pytestmark = pytest.mark.django_db


def _ref(name):
    row = IrModelData.objects.filter(module='base', name=name).first()
    return ReportPaperformat.objects.get(pk=row.res_id) if row else None


def test_the_euro_format_has_the_source_values():
    euro = _ref('paperformat_euro')
    assert euro is not None
    assert (euro.name, euro.format, euro.default, euro.orientation) == (
        'A4', 'A4', True, 'Portrait')
    assert (euro.margin_top, euro.margin_bottom, euro.margin_left,
            euro.margin_right) == (52, 32, 0, 0)
    assert (euro.header_spacing, euro.dpi, euro.css_margins) == (52, 90, True)
    assert _ref('paperformat_us').format == 'Letter'
    assert _ref('paperformat_batch_deposit').margin_top == 15


def test_a_second_seed_neither_duplicates_nor_overwrites():
    euro = _ref('paperformat_euro')
    euro.margin_top = 10
    euro.save()
    count = ReportPaperformat.objects.count()
    seed(connection.alias)
    assert ReportPaperformat.objects.count() == count
    euro.refresh_from_db()
    assert euro.margin_top == 10


def test_company_init_gives_the_euro_format_to_a_company_without_one():
    company = ResCompany.objects.create(name='Sin formato', code='nofmt')
    other = ReportPaperformat.objects.create(name='Otro')
    kept = ResCompany.objects.create(name='Con formato', code='withfmt',
                                     paperformat=other)
    ResCompany.objects.filter(pk=company.pk).update(paperformat=None)
    ResCompany.init(using=connection.alias)
    company.refresh_from_db()
    kept.refresh_from_db()
    assert company.paperformat_id == _ref('paperformat_euro').pk
    assert kept.paperformat_id == other.pk


def test_company_init_without_the_euro_format_assigns_nothing():
    company = ResCompany.objects.create(name='Sin formato', code='nofmt2')
    ResCompany.objects.filter(pk=company.pk).update(paperformat=None)
    IrModelData.objects.filter(module='base',
                               name='paperformat_euro').delete()
    ResCompany.init(using=connection.alias)
    company.refresh_from_db()
    assert company.paperformat_id is None


def test_init_models_runs_the_company_init():
    """≙ ``model.init()`` tras ``_auto_init`` en ``init_models``
    (``odoo19c: odoo/orm/registry.py:751-752``): el gancho de la compañía se
    ejecuta por la vía del registro, no sólo llamado a mano."""
    company = ResCompany.objects.create(name='Sin formato', code='nofmt3')
    ResCompany.objects.filter(pk=company.pk).update(paperformat=None)
    registry = Registry(connection.alias)
    with connection.cursor() as cr:
        registry.init_models(cr, ['res.company'], {'module': 'base'},
                             install=False)
    company.refresh_from_db()
    assert company.paperformat_id == _ref('paperformat_euro').pk
