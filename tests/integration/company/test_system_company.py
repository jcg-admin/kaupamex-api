"""Compañía de sistema + empresa de bootstrap (SOL-085 S3, lección L-EXT-3).

La *system company* (``is_system=True``) hospeda los datos compartidos de
plataforma (L-EXT-3: system company + fallback, NO ``company_id`` nullable) y
es la única compañía que el código nombra: su código es DATO del operador L0
(``SYSTEM_COMPANY_CODE``).

La primera empresa **L1** ya no se nombra en código (DEC-3 de
``tenants-sin-clases-en-codigo``): ``FOUNDER_COMPANY_CODE`` y
``ResCompany.get_founder()`` se eliminaron. Se declara en config
(``BOOTSTRAP_COMPANY_CODE``) y la crea el bootstrap — mecanismo que este
archivo verifica junto al de la system company.
"""
import pytest
from django.test import override_settings

from addons.sale_subscription.data.res_company_data import (
    SYSTEM_COMPANY_CODE,
    seed as bootstrap_company_seed,
)
from addons.base.models import ResCompany

pytestmark = pytest.mark.django_db


def test_is_system_defaults_false():
    c = ResCompany.objects.create(code='acme', name='Acme')
    c.refresh_from_db()
    assert c.is_system is False


def test_get_system_creates_idempotent():
    a = ResCompany.get_system()
    b = ResCompany.get_system()
    assert a.pk == b.pk
    assert a.code == SYSTEM_COMPANY_CODE
    assert a.is_system is True


def test_bootstrap_company_is_created_from_config():
    with override_settings(BOOTSTRAP_COMPANY_CODE='primera-l1',
                           BOOTSTRAP_COMPANY_NAME='Primera L1'):
        company = bootstrap_company_seed()
        again = bootstrap_company_seed()
    assert company is not None
    assert company.code == 'primera-l1'
    assert again.pk == company.pk               # idempotente
    # Es una empresa L1 real, no la system company de datos compartidos.
    assert company.is_system is False


def test_bootstrap_company_is_distinct_from_the_system_company():
    with override_settings(BOOTSTRAP_COMPANY_CODE='otra-l1',
                           BOOTSTRAP_COMPANY_NAME='Otra L1'):
        company = bootstrap_company_seed()
    assert ResCompany.get_system().pk != company.pk


def test_no_company_is_seeded_when_config_declares_none():
    """Una instalación sin empresa declarada no fabrica ninguna.

    Es el cambio de fondo de DEC-3: antes ``get_founder()`` creaba una empresa
    concreta bajo demanda en cualquier deployment.
    """
    with override_settings(BOOTSTRAP_COMPANY_CODE=''):
        assert bootstrap_company_seed() is None
