"""Founder + system company (SOL-085 S3, lección L-EXT-3).

Antes de colgar la FK ``company`` a los modelos de dominio (S3), hace falta el
**target de backfill**: la *founder company* (PracticaYoruba, el primer tenant
L1 real) para las filas existentes, y la *system company* (``is_system=True``)
para los datos compartidos de plataforma (L-EXT-3: system company + fallback,
NO ``company_id`` nullable). Ambos helpers son idempotentes.
"""
import pytest

from addons.sale_subscription.data.res_company_data import (
    FOUNDER_COMPANY_CODE,
    SYSTEM_COMPANY_CODE,
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


def test_get_founder_creates_idempotent():
    a = ResCompany.get_founder()
    b = ResCompany.get_founder()
    assert a.pk == b.pk
    assert a.code == FOUNDER_COMPANY_CODE
    # La founder es un tenant real (no la system company de datos compartidos).
    assert a.is_system is False


def test_system_and_founder_are_distinct():
    assert ResCompany.get_system().pk != ResCompany.get_founder().pk
