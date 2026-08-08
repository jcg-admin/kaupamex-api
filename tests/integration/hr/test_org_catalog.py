"""hr.department / hr.job — núcleo organizativo (Odoo ``hr``).

Re-hogar de ``platform.Department``/``platform.Job`` a su familia fiel ``hr``
(``analisis-porte-familia-hr``). ``subsidiary`` se disolvió (D-1 cerrada):
la referencia no lo declara en ``hr.department`` — la multi-entidad-legal es
la jerarquía de ``res.company`` (Branches), y el departamento sólo lleva
``company_id``. ``is_active`` → ``active`` (D-3); ``Job.title`` →
``HrJob.name`` (D-3).

Invariante de jerarquía (DIS-04): un departamento no puede ser su propio padre
ni cerrar un ciclo (``DEPARTMENT_CYCLE``) — el helper vive ahora en
``addons.base`` (D-4).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models import ResCompany, ResCurrency
from addons.hr.models import HrDepartment, HrJob

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    mxn, _ = ResCurrency.objects.get_or_create(name='MXN', defaults={'symbol': '$'})
    return ResCompany.create_company('Acme', currency=mxn, code='acme')


# --- HrDepartment -----------------------------------------------------------

def test_department_with_company(company):
    d = HrDepartment.objects.create(name='Ventas', company=company)
    d.refresh_from_db()
    assert d.company_id == company.pk
    assert d.active is True
    assert str(d) == 'Ventas'


def test_department_without_company():
    # company es opcional (SET_NULL), como el resto de FKs de compañía.
    d = HrDepartment.objects.create(name='Corporativo')
    d.refresh_from_db()
    assert d.company_id is None


def test_department_subhierarchy(company):
    ventas = HrDepartment.objects.create(name='Ventas', company=company)
    online = HrDepartment.objects.create(
        name='Ventas Online', parent=ventas, company=company)
    assert online.parent_id == ventas.pk
    assert list(ventas.children.all()) == [online]


def test_department_no_self_cycle(company):
    d = HrDepartment.objects.create(name='Ventas', company=company)
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
    d = HrDepartment.objects.create(name='Ventas', company=company)
    j = HrJob.objects.create(name='Vendedor', department=d, company=company)
    assert j.department_id == d.pk
    assert j.company_id == company.pk
