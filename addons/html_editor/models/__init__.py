"""Modelos del addon ``html_editor`` — un archivo por modelo, como la fuente.

Puerto de Odoo Community ``html_editor/models/`` (``odoo19c:``, LGPL-3). Los
**nueve** archivos de la referencia están presentes y con su nombre:

============================  ==========================================
Archivo                        Qué porta
============================  ==========================================
``diff_utils.py``              el formato de parche y el *diff* de HTML
``html_field_history_mixin``   el historial de revisiones de un campo
``ir_attachment.py``           la imagen vista por el editor
``ir_http.py``                 las tres banderas de edición de la URL
``ir_qweb_fields.py``          los conversores en la dirección de vuelta
``ir_ui_view.py``              guardar lo que se editó
``ir_websocket.py``            el canal de coedición y su guarda de acceso
``models.py``                  dos atributos de campo para la vista
``test_models.py``             el modelo con un campo por tipo
============================  ==========================================

**Cinco de los nueve extienden modelos ajenos** —``ir.attachment``,
``ir.http``, ``ir.qweb``/``ir.qweb.field.*``, ``ir.ui.view``,
``ir.websocket``— y por eso publican un ``apply_html_editor_extensions()`` que
``HtmlEditorConfig.ready()`` invoca, cada uno bajo un alias distinto. La
excepción es ``models.py``, que extiende ``base``: también publica el suyo.

**Sólo ``test_models.py`` declara tabla.** Es el único origen de migración de
este addon.

El censo símbolo a símbolo, las divergencias y sus sucesores viven en el
docstring de cada archivo — no se resumen aquí para que haya una sola fuente.
"""
from .diff_utils import (
    apply_patch,
    generate_comparison,
    generate_patch,
    generate_unified_diff,
)
from .html_field_history_mixin import HtmlFieldHistoryMixin
from .ir_attachment import SUPPORTED_IMAGE_MIMETYPES
from .ir_websocket import (
    EDITOR_COLLABORATION,
    IrWebsocket,
    editor_collaboration_channel,
)
from .test_models import (
    Html_EditorConverterTest,
    Html_EditorConverterTestSub,
)

__all__ = [
    'EDITOR_COLLABORATION',
    'HtmlFieldHistoryMixin',
    'IrWebsocket',
    'Html_EditorConverterTest',
    'Html_EditorConverterTestSub',
    'SUPPORTED_IMAGE_MIMETYPES',
    'apply_patch',
    'editor_collaboration_channel',
    'generate_comparison',
    'generate_patch',
    'generate_unified_diff',
]
