"""Org catalog HR-core — Subsidiary / Department / Job (UC-PLT-14, DIS-01/02).

Primera rebanada del módulo Employee Management (familia HR): la estructura
organizativa del tenant vive junto a ``Company`` (``apps.platform.company``),
no en ``users`` — la dependencia es ``users → platform.company`` (diseño
:ref:`diseno-modelo-organizacion-hr-core`, DIS-01).

- ``Subsidiary`` = entidad legal bajo la Company (jerarquía OneWorld → root).
- ``Department`` = unidad org dentro de una subsidiaria (sub-departamentos).
- ``Job`` = catálogo de puestos.

Invariante de jerarquía (DIS-04, extendido a org): un nodo no puede ser su
propio padre ni cerrar un ciclo (``SUBSIDIARY_CYCLE`` / ``DEPARTMENT_CYCLE``).
"""
import pytest
from django.core.exceptions import ValidationError

from apps.platform.company.models import (
    Company,
    Department,
    Job,
    Subsidiary,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return Company.objects.create(code='acme', name='Acme')


# --- Subsidiary -------------------------------------------------------------

def test_subsidiary_is_active_default_true(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    s.refresh_from_db()
    assert s.is_active is True
    assert str(s) == 'Acme MX'


def test_subsidiary_hierarchy_parent_child(company):
    root = Subsidiary.objects.create(company=company, name='Acme Global')
    child = Subsidiary.objects.create(company=company, name='Acme MX', parent=root)
    assert child.parent_id == root.pk
    assert list(root.children.all()) == [child]


def test_subsidiary_cannot_be_its_own_parent(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    s.parent = s
    with pytest.raises(ValidationError) as exc:
        s.full_clean()
    assert 'SUBSIDIARY_CYCLE' in str(exc.value)


def test_subsidiary_no_cycle_in_chain(company):
    a = Subsidiary.objects.create(company=company, name='A')
    b = Subsidiary.objects.create(company=company, name='B', parent=a)
    # Cerrar el ciclo A → B → A debe rechazarse.
    a.parent = b
    with pytest.raises(ValidationError) as exc:
        a.full_clean()
    assert 'SUBSIDIARY_CYCLE' in str(exc.value)


# --- Department -------------------------------------------------------------

def test_department_belongs_to_subsidiary(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    d = Department.objects.create(subsidiary=s, name='Ventas')
    d.refresh_from_db()
    assert d.subsidiary_id == s.pk
    assert d.is_active is True
    assert str(d) == 'Ventas'


def test_department_subhierarchy(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    ventas = Department.objects.create(subsidiary=s, name='Ventas')
    online = Department.objects.create(subsidiary=s, name='Ventas Online', parent=ventas)
    assert online.parent_id == ventas.pk
    assert list(ventas.children.all()) == [online]


def test_department_no_self_cycle(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    d = Department.objects.create(subsidiary=s, name='Ventas')
    d.parent = d
    with pytest.raises(ValidationError) as exc:
        d.full_clean()
    assert 'DEPARTMENT_CYCLE' in str(exc.value)


# --- Job --------------------------------------------------------------------

def test_job_department_is_optional(company):
    j = Job.objects.create(title='Analista')
    j.refresh_from_db()
    assert j.department_id is None
    assert j.is_active is True
    assert str(j) == 'Analista'


def test_job_bound_to_department(company):
    s = Subsidiary.objects.create(company=company, name='Acme MX')
    d = Department.objects.create(subsidiary=s, name='Ventas')
    j = Job.objects.create(title='Vendedor', department=d)
    assert j.department_id == d.pk
