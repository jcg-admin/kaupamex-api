"""Datos de ``account_payment`` — un archivo, un ``<record>`` de la
referencia:

- ``config_parameters.py`` → ``enable_portal_payment`` (≙ ``data/
  ir_config_parameter.xml``).
"""
from .config_parameters import ENABLE_PORTAL_PAYMENT_KEY, seed_config_parameters

__all__ = ['ENABLE_PORTAL_PAYMENT_KEY', 'seed_config_parameters']
