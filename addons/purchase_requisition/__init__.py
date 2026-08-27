"""Addon ``purchase_requisition`` — el acuerdo de compra y sus alternativas.

Adaptación de Odoo ``purchase_requisition`` (``odoo19c:
addons/purchase_requisition/``, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

**Sin imports a propósito**, aunque la fuente sí los tenga (``from . import
models`` / ``from . import wizard``, ``odoo19c: :3-4``). Es el patrón del árbol
(``addons/utm/__init__.py`` es la plantilla): importar ``models`` aquí lo
cargaría en tiempo de import del paquete, y ``PurchaseRequisitionConfig`` ya lo
importa por su cuenta —Django importa ``<app>.models`` al poblar el registro—
además de aplicar las extensiones en ``ready()``.
"""
