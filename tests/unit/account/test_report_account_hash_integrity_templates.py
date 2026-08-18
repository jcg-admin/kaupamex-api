"""``report.account.report_hash_integrity`` -- ensamblador de valores.

Cubre ``addons/account/report/account_hash_integrity_templates.py`` (tarea
#398, hallazgo H-API-682). El unico metodo esta BLOQUEADO -- ver su
docstring -- asi que el contrato que se prueba aqui es que el bloqueo sea
RUIDOSO (``NotImplementedError`` con el motivo citado), no silencioso.

**Instanciar el modelo YA es acceso a base**, aunque no se persista.
Django resuelve **todos** los ``default`` en ``Model.__init__``
(``django/db/models/base.py:558``), y ``stock`` le cuelga a ``ResCompany``
un ``confirmation_mail_template`` cuyo default consulta
(``addons/stock/models/res_company.py:148``). Por eso la clase que
construye un ``ResCompany()`` lleva ``django_db``: el guard de tipo, que
sólo recibe un ``object()``, no lo necesita.
"""
import pytest

from addons.account.report.account_hash_integrity_templates import (
    REPORT_NAME,
    ReportAccountReportHashIntegrity,
)
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit]


def test_report_name_matches_the_source():
    """``odoo19c:
    addons/account/report/account_hash_integrity_templates.py:9``."""
    assert REPORT_NAME == 'account.report_hash_integrity'


class TestGetReportValuesTypeGuard:
    def test_rejects_a_non_res_company_argument(self):
        with pytest.raises(TypeError):
            ReportAccountReportHashIntegrity._get_report_values(
                company=object(), docids=[1])


@pytest.mark.django_db
class TestGetReportValuesBlocked:
    """``ResCompany._check_hash_integrity`` no existe -- ver el docstring
    del modulo bajo prueba para la cita PROVEN del hueco.

    Lleva ``django_db`` porque construye un ``ResCompany()`` -- ver la
    cabecera del modulo.
    """

    def test_raises_loudly_instead_of_a_silent_empty_result(self):
        company = ResCompany()  # sin persistir: no toca la base
        with pytest.raises(NotImplementedError) as excinfo:
            ReportAccountReportHashIntegrity._get_report_values(
                company=company, docids=[1])
        assert '_check_hash_integrity' in str(excinfo.value)

    def test_does_not_have_the_hash_integrity_method_today(self):
        """Ancla la premisa del bloqueo: si este assert alguna vez falla,
        significa que ``_check_hash_integrity`` ya se porto en
        ``addons/account/models/res_company.py`` y este archivo debe
        desbloquearse (tarea #510).
        """
        company = ResCompany()
        assert not hasattr(company, '_check_hash_integrity')
