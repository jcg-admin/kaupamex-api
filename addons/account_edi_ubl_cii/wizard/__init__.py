"""Asistentes del addon ``account_edi_ubl_cii``.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/wizard/__init__.py``
(``odoo-tools@622ddc2a``, LGPL-3, 1 línea) — atribución y aviso de licencia
preservados (DEC-KX-03).

El único archivo del paquete **extiende** ``account.move.send.wizard`` (no
declara modelo propio), así que NO se importa aquí: lo carga
``AccountEdiUblCiiConfig.ready()``, mismo criterio que
``account_edi/wizard/__init__.py``.
"""
