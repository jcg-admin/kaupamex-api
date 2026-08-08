"""Datos semilla del addon ``account_test`` — un archivo, un XML de origen
(fiel al único ``data/accounting_assert_test_data.xml`` de la referencia)."""
from .accounting_assert_tests import TESTS, seed_accounting_assert_tests

__all__ = [
    'TESTS',
    'seed_accounting_assert_tests',
]
