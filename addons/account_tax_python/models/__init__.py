"""Modelos del addon ``account_tax_python`` — paquete espejo de
``models/`` (referencia).

Un solo modelo declarado normal (``AccountTaxFormula``, para que Django lo
descubra en la fase de carga de apps y lo incluya en migraciones). El
monkeypatch sobre ``account.AccountTax``/``AccountTaxQuerySet`` vive en
``account_tax_extensions.py``, importado sólo desde
``AccountTaxPythonConfig.ready()`` — NO desde aquí (mismo criterio que
``account_debit_note/models/__init__.py`` separa su modelo de sus ganchos
de numeración: el registro de apps aún no está poblado en tiempo de import
de ``models/__init__.py``).
"""
from .account_tax import AccountTaxFormula

__all__ = ['AccountTaxFormula']
