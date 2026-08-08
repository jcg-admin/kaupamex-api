"""Las etiquetas de impuesto que crea el propio acto de definir una expresión.

Portación de ``odoo19c: account/models/account_report.py:695-720`` y
``account_account_tag.py:78-95`` (``odoo-tools@622ddc2a``, LGPL-3).

El mecanismo que estos tests fijan es el que :ref:`h-api-358` destapó: el CSV
de impuestos de una localización cita etiquetas **por nombre suelto**, y quien
las crea no es un catálogo de datos sino ``AccountReportExpression`` al
guardarse con ``engine='tax_tags'``. Sin él, cargar el plan mexicano deja sus
138 impuestos con cero enlaces de reparto — en verde y sin señal.
"""
import pytest

from addons.account.models import (
    AccountAccountTag,
    AccountReport,
    AccountReportExpression,
    AccountReportLine,
)

pytestmark = pytest.mark.django_db


def _report_line(name='DIOT'):
    """Un reporte con una línea, que es el mínimo que cuelga una expresión."""
    report = AccountReport.objects.create(name=name)
    return AccountReportLine.objects.create(report=report, name=f'{name} línea')


class TestGetTaxTagsDomain:
    """``get_tax_tags_domain`` — el filtro. ≙ ``_get_tax_tags_domain``."""

    def test_strips_the_leading_minus_from_the_formula(self):
        """El signo pertenece a la fórmula, no al nombre de la etiqueta.

        ``-DIOT: 16%`` y ``DIOT: 16%`` designan la MISMA etiqueta con signo
        opuesto en el reparto. La referencia lo resuelve con ``lstrip('-')``
        (``odoo19c: account_account_tag.py:92``); si el puerto guardara el
        signo, cada fórmula negativa crearía una etiqueta huérfana.
        """
        assert (AccountAccountTag.get_tax_tags_domain('-DIOT: 16%', None)
                == AccountAccountTag.get_tax_tags_domain('DIOT: 16%', None))

    def test_restricts_to_tax_applicability(self):
        """Una etiqueta de cuenta con el mismo nombre no debe casar."""
        AccountAccountTag.objects.create(
            name='DIOT: 16%', applicability='accounts')
        assert not AccountAccountTag.get_tax_tags('DIOT: 16%', None).exists()


class TestGetTaxTags:
    """``get_tax_tags`` — la búsqueda. ≙ ``_get_tax_tags``."""

    def test_finds_the_tag_by_name_and_applicability(self):
        tag = AccountAccountTag.objects.create(
            name='DIOT: Retención', applicability='taxes')
        found = AccountAccountTag.get_tax_tags('DIOT: Retención', None)
        assert list(found) == [tag]

    def test_finds_inactive_tags_too(self):
        """``active_test=False`` en la referencia: una etiqueta archivada sigue
        existiendo, y volver a crearla duplicaría la fila."""
        tag = AccountAccountTag.objects.create(
            name='DIOT: Exento', applicability='taxes', active=False)
        assert list(AccountAccountTag.get_tax_tags('DIOT: Exento', None)) == [tag]


class TestCreateTaxTags:
    """``create_tax_tags`` — la creación idempotente. ≙ ``_create_tax_tags``."""

    def test_creates_the_tag_when_absent(self):
        AccountReportExpression.create_tax_tags('DIOT: 16% TAX', None)
        assert AccountAccountTag.objects.filter(
            name='DIOT: 16% TAX', applicability='taxes').count() == 1

    def test_is_idempotent(self):
        """Dos expresiones pueden citar la misma etiqueta; la segunda no crea."""
        AccountReportExpression.create_tax_tags('DIOT: 16%', None)
        AccountReportExpression.create_tax_tags('DIOT: 16%', None)
        assert AccountAccountTag.objects.filter(name='DIOT: 16%').count() == 1


class TestExpressionSaveCreatesItsTag:
    """El disparador: guardar la expresión crea su etiqueta.

    ≙ el ``create()`` sobreescrito de la referencia
    (``odoo19c: account_report.py:704-720``). Es lo que hace que definir el
    reporte DIOT baste para que el plan fiscal resuelva sus 21 nombres.
    """

    def test_creates_the_tag_for_a_tax_tags_expression(self):
        AccountReportExpression.objects.create(
            report_line=_report_line(), label='balance',
            engine='tax_tags', formula='DIOT: 8% N.')
        assert AccountAccountTag.objects.filter(
            name='DIOT: 8% N.', applicability='taxes').exists()

    def test_does_not_create_a_tag_for_another_engine(self):
        """Sólo ``tax_tags`` nombra una etiqueta; en los demás motores la
        fórmula es un dominio o una agregación, no un nombre."""
        AccountReportExpression.objects.create(
            report_line=_report_line(), label='balance',
            engine='domain', formula="[('account_id.code', '=like', '1%')]")
        assert not AccountAccountTag.objects.filter(applicability='taxes').exists()

    def test_saving_the_expression_again_does_not_duplicate_the_tag(self):
        expression = AccountReportExpression.objects.create(
            report_line=_report_line(), label='balance',
            engine='tax_tags', formula='DIOT: Refunds')
        expression.blank_if_zero = True
        expression.save()
        assert AccountAccountTag.objects.filter(name='DIOT: Refunds').count() == 1

    def test_takes_the_country_from_the_report(self):
        """La etiqueta hereda el país del reporte — ≙
        ``expression.report_line_id.report_id.country_id``.

        Con ``country=None`` (este árbol no siembra países, ver
        :ref:`h-api-358`) la etiqueta nace sin país y ``get_tax_tags`` la
        encuentra con el mismo valor: el par crear/buscar es coherente, que es
        lo que el mecanismo necesita.
        """
        line = _report_line()
        AccountReportExpression.objects.create(
            report_line=line, label='balance',
            engine='tax_tags', formula='DIOT: 0%')
        tag = AccountAccountTag.objects.get(name='DIOT: 0%')
        assert tag.country == line.report.country
