"""Modelos del addon ``account_payment`` — los 4 RELATED de ``links.py`` (los
únicos que Django necesita descubrir para migrar) más 7 archivos-espejo de
la referencia (``odoo19c: account_payment/models/*.py``) que sólo cuelgan
comportamiento — **deliberadamente no importados aquí**.

Mismo criterio que ``account_debit_note/models/__init__.py``: un archivo que
cuelga propiedades/métodos sobre un modelo ajeno (``setattr``/
``chain_method``) se importa SIEMPRE desde ``AccountPaymentConfig.ready()``,
nunca desde este ``__init__``, para no depender del orden de
``INSTALLED_APPS`` ni arriesgar ``AppRegistryNotReady``.
"""
from .links import (
    AccountMoveTransactionLink,
    AccountPaymentMethodLineProvider,
    AccountPaymentTransaction,
    PaymentGatewayJournal,
)

__all__ = [
    'AccountPaymentTransaction',
    'AccountMoveTransactionLink',
    'AccountPaymentMethodLineProvider',
    'PaymentGatewayJournal',
]
