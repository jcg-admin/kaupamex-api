"""Modelos de ``base_setup`` — el formulario de ajustes generales.

No declara tablas propias. ``ResConfigSettings`` es la extensión del formulario
compartido —abstracta, como en la fuente— y ``SiteConfigSettings`` el único
formulario **concreto** del árbol, transitorio igual que el
``res.config.settings`` de la referencia (``TransientModel`` medido por símbolo
en ``odoo19c:`` y ``odoo18c:``). Sus valores viven en los destinos.

``KpiProvider`` e ``IrHttp`` son abstractos; la extensión de ``res.users`` no es
una clase sino una instalación (ver ``res_users.py``) y por eso no se exporta
un símbolo de modelo.
"""
from .ir_http import IrHttp
from .kpi_provider import KpiProvider
from .res_config_settings import ResConfigSettings, SiteConfigSettings

__all__ = ['IrHttp', 'KpiProvider', 'ResConfigSettings', 'SiteConfigSettings']
