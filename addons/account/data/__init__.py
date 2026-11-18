"""Datos de arranque de ``account`` — ≙ el ``data/`` del addon de referencia.

Allá son archivos XML que el cargador de módulos aplica al instalar
(``odoo19c: account/data/account_data.xml``, ``odoo-tools@622ddc2a``). Aquí
cada bloque es un módulo Python con su especificación, y una data-migration lo
aplica. El mecanismo de entrega es el que fijó :ref:`h-api-263`; su límite
—no sobrevive al ``flush`` de la suite— está medido en :ref:`h-api-337`, así
que ningún test afirma sobre estas filas: los tests siembran las suyas.
"""

from .account_tags import MASTER_ACCOUNT_TAGS, seed_account_tags
from .payment_methods import (MANUAL_PAYMENT_METHODS,
                              seed_manual_payment_methods)
from .sequences import PAYMENT_SEQUENCE, seed_payment_sequence

__all__ = ['MANUAL_PAYMENT_METHODS', 'MASTER_ACCOUNT_TAGS',
           'PAYMENT_SEQUENCE', 'seed_account_tags',
           'seed_manual_payment_methods', 'seed_payment_sequence']
