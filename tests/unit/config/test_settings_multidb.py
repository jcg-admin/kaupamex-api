"""Wiring multi-DB en settings (SOL-091, T-091-05).

Verifica que ``config/settings/base.py`` cablea el router y aplica el loader.
En el entorno de testing (N=1, sin bases ``company_<N>_db`` en el roster) la
neutralidad se mantiene: ``DATABASES`` sólo tiene ``default``.
"""
import re

from django.conf import settings


def test_database_routers_wired_to_company_router():
    assert settings.DATABASE_ROUTERS == ['orm.routers.CompanyDatabaseRouter']


def test_n1_neutrality_only_default_alias_by_default():
    company_aliases = [a for a in settings.DATABASES if re.match(r'^company_\d+_db$', a)]
    assert company_aliases == []
    assert 'default' in settings.DATABASES
