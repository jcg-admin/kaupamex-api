"""``ReportPaperformat`` — atributos de clase y la relación inversa que
``ir_actions_report.py`` dejó pendiente.

El bullet de ``report_ids`` afirmaba su cierre con un conteo de clases
(``grep -rn "^class IrActionsReport\b" src/`` → 1), que sólo prueba que la
clase EXISTE — no que la relación devuelva lo que debe. Sub-patrón D de
``metrica-decide-la-conclusion.md``: un conteo así pasa igual si el
``related_name`` estuviera mal escrito o apuntara a otro modelo. Los casos de
este archivo discriminan devolviendo dos ``paperformat`` y comprobando que
cada uno ve SÓLO sus propios reportes, no que ``report_ids`` "no truene".

``_name``/``_description`` — atributos de clase de ``odoo19c: odoo/addons/
base/models/report_paperformat.py:166-167`` que el archivo no declaraba pese
a que ``atributos-de-clase-de-modelo.md`` los exige verbatim junto a su forma
Django (``Meta.db_table`` derivado de ``_name``).
"""
import pytest

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.report_paperformat import ReportPaperformat

pytestmark = pytest.mark.django_db


def _paperformat(**fields):
    fields.setdefault('name', 'A4 de prueba')
    fields.setdefault('format', 'A4')
    return ReportPaperformat.objects.create(**fields)


def _report(**fields):
    fields.setdefault('name', 'Reporte de prueba')
    fields.setdefault('model', 'res.partner')
    fields.setdefault('report_name', 'base.report_x')
    fields.setdefault('report_type', 'qweb-pdf')
    return IrActionsReport.objects.create(**fields)


class TestTheClassAttributesMatchTheReference:
    """``_name``/``_description`` — verbatim, con su forma Django en Meta."""

    def test_the_name_matches_the_reference(self):
        assert ReportPaperformat._name == 'report.paperformat'

    def test_the_description_matches_the_reference(self):
        assert ReportPaperformat._description == 'Paper Format Config'

    def test_the_table_derives_from_the_name(self):
        assert (ReportPaperformat._meta.db_table
                == ReportPaperformat._name.replace('.', '_'))


class TestReportIdsSeesOnlyItsOwnReports:
    """``report_ids`` — el ``One2many`` que apareció solo, por su lado."""

    def test_a_paperformat_with_no_reports_has_an_empty_report_ids(self):
        empty = _paperformat(name='Sin reportes')
        assert list(empty.report_ids.all()) == []

    def test_a_linked_report_shows_up_on_its_own_paperformat_only(self):
        mine = _paperformat(name='Mío')
        other = _paperformat(name='Ajeno')
        linked = _report(paperformat_id=mine)
        _report(paperformat_id=other, name='Otro reporte', report_name='base.report_y')

        assert list(mine.report_ids.all()) == [linked]
        assert list(other.report_ids.all()) != [linked]

    def test_unlinking_the_report_clears_it_from_report_ids(self):
        paperformat = _paperformat(name='Con y sin')
        report = _report(paperformat_id=paperformat)
        assert list(paperformat.report_ids.all()) == [report]

        report.paperformat_id = None
        report.save()

        assert list(paperformat.report_ids.all()) == []
