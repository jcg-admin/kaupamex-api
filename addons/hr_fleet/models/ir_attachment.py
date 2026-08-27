"""``ir.attachment`` — previsualizar un adjunto en pestaña nueva.

Adaptación de Odoo hr_fleet/models/ir_attachment.py
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 14 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte NO APLICABLE DECLARADO — 0 de 1 símbolo
===============================================

El único símbolo de la referencia, ``action_preview_attachment``
(``:9-14``), devuelve un ``ir.actions.act_url`` hacia
``/web/content/<id>/<name>`` con ``target: 'new'`` — es navegación del
cliente Odoo (abrir el adjunto en otra pestaña), la misma familia que los
``ir.actions.act_window`` que ``account_fleet`` y el resto de este addon
declaran no portables (DRF headless: la URL de descarga de un adjunto la
compone la vista DRF que exponga ``ir.attachment``, no el modelo).

El archivo existe para espejar el conjunto de archivos de la referencia
(regla del SITIO, H-API-578) y dejar el desenlace greppeable.
"""


def apply_hr_fleet_ir_attachment_extensions():
    """No-op declarado — el único símbolo es navegación de cliente (ver
    docstring; mismo patrón que
    ``apply_hr_mail_activity_plan_template_extensions`` de ``hr``)."""
    return None
