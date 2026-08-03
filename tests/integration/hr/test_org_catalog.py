"""hr.department / hr.job — núcleo organizativo (Odoo ``hr``).

Re-hogar de ``platform.Department``/``platform.Job`` a su familia fiel ``hr``
(``analisis-porte-familia-hr``). Cambios respecto del origen: FK directa
opcional a ``platform.Company`` (D-2); ``subsidiary`` opcional (D-2);
``is_active`` → ``active`` (D-3); ``Job.title`` → ``HrJob.name`` (D-3).

Invariante de jerarquía (DIS-04): un departamento no puede ser su propio padre
ni cerrar un ciclo (``DEPARTMENT_CYCLE``) — el helper vive ahora en
``addons.base`` (D-4).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.platform.models import Company, Subsidiary
from addons.hr.models import HrDepartment, HrJob

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return Company.objects.create(code='acme', name='Acme')


# --- HrDepartment -----------------------------------------------------------

def test_department_optional_subsidiary_and_company(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    d = HrDepartment.objects.create(subsidiary=s, name='Ventas', company=company)
    d.refresh_from_db()
    assert d.subsidiary_id == s.pk
    assert d.company_id == company.pk
    assert d.active is True
    assert str(d) == 'Ventas'


def test_department_without_subsidiary(company):
    # D-2: subsidiary ya no es el ancla; puede crearse sin ella.
    d = HrDepartment.objects.create(name='Corporativo', company=company)
    d.refresh_from_db()
    assert d.subsidiary_id is None
    assert d.company_id == company.pk


def test_department_subhierarchy(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    ventas = HrDepartment.objects.create(subsidiary=s, name='Ventas')
    online = HrDepartment.objects.create(
        subsidiary=s, name='Ventas Online', parent=ventas)
    assert online.parent_id == ventas.pk
    assert list(ventas.children.all()) == [online]


def test_department_no_self_cycle(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    d = HrDepartment.objects.create(subsidiary=s, name='Ventas')
    d.parent = d
    with pytest.raises(ValidationError) as exc:
        d.full_clean()
    assert 'DEPARTMENT_CYCLE' in str(exc.value)


# --- HrJob ------------------------------------------------------------------

def test_job_department_is_optional(company):
    j = HrJob.objects.create(name='Analista')
    j.refresh_from_db()
    assert j.department_id is None
    assert j.active is True
    assert str(j) == 'Analista'


def test_job_bound_to_department(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    d = HrDepartment.objects.create(subsidiary=s, name='Ventas')
    j = HrJob.objects.create(name='Vendedor', department=d, company=company)
    assert j.department_id == d.pk
    assert j.company_id == company.pk
