"""Founder + system company (SOL-085 S3, lección L-EXT-3).

Antes de colgar la FK ``company`` a los modelos de dominio (S3), hace falta el
**target de backfill**: la *founder company* (PracticaYoruba, el primer tenant
L1 real) para las filas existentes, y la *system company* (``is_system=True``)
para los datos compartidos de plataforma (L-EXT-3: system company + fallback,
NO ``company_id`` nullable). Ambos helpers son idempotentes.
"""
import pytest

from addons.platform.models import (
    FOUNDER_COMPANY_CODE,
    SYSTEM_COMPANY_CODE,
    Company,
)

pytestmark = pytest.mark.django_db


def test_is_system_defaults_false():
    c = Company.objects.create(code='acme', name='Acme')
    c.refresh_from_db()
    assert c.is_system is False


def test_get_system_creates_idempotent():
    a = Company.get_system()
    b = Company.get_system()
    assert a.pk == b.pk
    assert a.code == SYSTEM_COMPANY_CODE
    assert a.is_system is True


def test_get_founder_creates_idempotent():
    a = Company.get_founder()
    b = Company.get_founder()
    assert a.pk == b.pk
    assert a.code == FOUNDER_COMPANY_CODE
    # La founder es un tenant real (no la system company de datos compartidos).
    assert a.is_system is False


def test_system_and_founder_are_distinct():
    assert Company.get_system().pk != Company.get_founder().pk
