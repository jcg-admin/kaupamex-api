"""Jerarquía de sucursales — ``res.company`` (antes ``Subsidiary``).

``Subsidiary`` se disolvió contra la referencia (D-1 cerrada): la
multi-entidad-legal es la jerarquía de ``res.company``
(``parent_id``/``child_ids`` — 'Branches', ``odoo19c: res_company.py:51-56``),
con ``parent_path`` como ruta materializada. Estas pruebas ejercen ese eje
sobre ``base.ResCompany``. ``Department``/``Job`` viven en ``hr``
(``tests/integration/hr/test_org_catalog.py``).
"""
import pytest

from addons.base.models import ResCompany, ResCurrency

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    # Bootstrap: la primera compañía no puede heredar moneda de una principal.
    mxn, _ = ResCurrency.objects.get_or_create(name='MXN', defaults={'symbol': '$'})
    return ResCompany.create_company('Acme', currency=mxn, code='acme')


def test_branch_parent_child(company):
    branch = ResCompany.create_company('Acme MX', code='acme-mx', parent=company)
    assert branch.parent_id == company.pk
    assert list(company.child_ids.all()) == [branch]


def test_parent_path_materializada(company):
    branch = ResCompany.create_company('Acme MX', code='acme-mx', parent=company)
    branch.refresh_from_db()
    assert branch.parent_path == f'{company.pk}/{branch.pk}/'
    assert list(branch.parent_ids.order_by('pk')) == [company, branch]
    assert branch.root_id == company


def test_branch_hereda_moneda_de_la_raiz(company):
    """``_get_company_root_delegated_field_names``: la sucursal copia la
    moneda funcional de su raíz."""
    branch = ResCompany.create_company('Acme MX', code='acme-mx', parent=company)
    branch.apply_root_delegation()
    assert branch.currency_id == company.currency_id
