"""Modelos del addon ``http_routing`` (estructura Odoo: un archivo por modelo).

Puerto de Odoo Community ``http_routing/`` (``odoo19c:``, LGPL-3). Los tres
archivos de modelo de la referencia están presentes; el censo símbolo a
símbolo, las divergencias y los tres sucesores (#274, #275, #276) viven en el
docstring de ``ir_http.py``.

Los tres extienden modelos de ``base`` —``ir.http``, ``ir.qweb``,
``res.lang``— y por eso ninguno declara tabla: este addon no tiene
migraciones.
"""
from .ir_http import (
    FrontendLangMiddleware,
    ModelConverter,
    apply_http_routing_extensions,
    model_converter_for,
    register_model_converter,
)
from .ir_qweb import apply_ir_qweb_extensions
from .res_lang import apply_res_lang_extensions

__all__ = [
    'FrontendLangMiddleware',
    'ModelConverter',
    'apply_http_routing_extensions',
    'apply_ir_qweb_extensions',
    'apply_res_lang_extensions',
    'model_converter_for',
    'register_model_converter',
]
