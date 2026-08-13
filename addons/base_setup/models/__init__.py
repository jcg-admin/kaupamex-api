"""Modelos de ``base_setup`` — el formulario de ajustes generales.

No declara tablas: ``SiteConfigSettings`` es un formulario transitorio, igual
que ``res.config.settings`` en la referencia (``TransientModel`` medido por
símbolo en ``odoo19c:`` y ``odoo18c:``). Sus valores viven en los destinos.
"""
from .res_config_settings import SiteConfigSettings

__all__ = ['SiteConfigSettings']
