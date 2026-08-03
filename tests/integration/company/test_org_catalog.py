"""Org catalog — Subsidiary (UC-PLT-14, DIS-01/02).

Estructura organizativa del tenant que vive junto a ``Company``
(``addons.platform``). ``Subsidiary`` = entidad legal bajo la Company
(jerarquía OneWorld → root). ``Department``/``Job`` re-hogaron al addon ``hr``
(``hr.department``/``hr.job``) — sus pruebas viven en
``tests/integration/hr/test_org_catalog.py`` (ver ``analisis-porte-familia-hr``).

Invariante de jerarquía (DIS-04): un nodo no puede ser su propio padre ni
cerrar un ciclo (``SUBSIDIARY_CYCLE``).
"""
import pytest
from django.core.exceptions import ValidationError

from addons.platform.models import Company, Subsidiary

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
