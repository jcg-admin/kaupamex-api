"""Modelos del addon ``web`` — paquete espejo de ``addons/web/models/``.

La referencia trae **un solo archivo**, ``models.py`` (2360 líneas, LGPL-3),
que extiende ``base`` (``_inherit = 'base'``) con la capa de datos del cliente
web: lectura/escritura por especificación (``web_read``/``web_save``),
búsqueda con paginado (``web_search_read``), agrupamiento para list/kanban
(``web_read_group`` y su familia de *formatters*), el widget de panel de
búsqueda (``search_panel_*``), el motor de ``onchange`` de formularios
dinámicos y el theming de reportes impresos (``ResCompany``).

Completado 2026-08-07 contra ``odoo-tools@622ddc2a`` (H-API-369, DEC-FW-04):
el addon era una cáscara de solo controladores. Ver la cabecera de
``models.py`` para la medición símbolo-por-símbolo, qué se adaptó a Django y
qué se declara ausente con su razón — no hay recorte silencioso.

- ``models.py`` → ``Base`` (mixin abstracto, ≙ ``_inherit = 'base'`` de la
  referencia — mismo estado no-wireado que ``addons.base.models.ir_model.Base``,
  su propio destino) + ``lazymapping`` + ``AND``/``OR``.
- ``base_document_layout.py`` → ``BaseDocumentLayout`` (``TransientModel``
  sin tabla — asistente de papelería/membrete, ``base.document.layout``).
- ``ir_http.py`` / ``res_partner.py`` extienden modelos de ``base`` vía
  ``_inherit`` (``apply_web_extensions()``, colgado desde
  ``WebConfig.ready()`` — ver ``apps.py``, no se importan aquí).
- ``ir_model.py`` extiende ``ir.model``: 0 de 5 métodos portados (todos
  declarados ausentes con razón) — sin código, no exporta símbolo.
"""
from .base_document_layout import BaseDocumentLayout  # noqa: F401
from .models import AND, OR, Base, lazymapping  # noqa: F401

__all__ = [
    'Base',
    'BaseDocumentLayout',
    'lazymapping',
    'AND',
    'OR',
]
