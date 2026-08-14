"""Modelos de ``account_add_gln`` — paquete espejo de
``odoo/addons/account_add_gln/models/``.

Un archivo, un modelo (monolito modular, como Odoo):

- ``res_partner.py`` → ``PartnerGln`` (GLN — RELATED OneToOne sobre
  ``base.ResPartner``, DEC-SALE-01).
"""
from .res_partner import PartnerGln

__all__ = ['PartnerGln']
