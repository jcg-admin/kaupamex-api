# -*- coding: utf-8 -*-
"""``account_check_printing.models`` — mapa de archivo → clase/extensión.

- ``res_currency.py``           → cuelga ``amount_to_text`` sobre ``base.ResCurrency``.
- ``account_payment_method.py`` → extiende ``_get_payment_method_information``.
- ``res_company.py``            → ``CheckPrintingCompanySettings`` (satélite ``res.company``).
- ``account_journal.py``        → ``CheckPrintingJournalSettings`` (satélite ``account.journal``).
- ``account_payment.py``        → ``CheckPrintingPaymentInfo`` (satélite ``account.payment``).

Los dos primeros SÓLO cuelgan funciones (``chain_method``, ver
``orm/method_chain.py``) — no declaran modelos propios, así que se aplican
desde ``AppConfig.ready()`` (``apps.py``), no aquí. Los tres últimos SÍ
declaran modelos con tabla propia: se importan aquí para que Django los
detecte al cargar la app (igual que cualquier ``models/__init__.py`` de
este árbol).
"""
from .res_company import CheckPrintingCompanySettings
from .account_journal import CheckPrintingJournalSettings
from .account_payment import CheckPrintingPaymentInfo

__all__ = [
    'CheckPrintingCompanySettings',
    'CheckPrintingJournalSettings',
    'CheckPrintingPaymentInfo',
]
