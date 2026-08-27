"""Addon ``account_edi_ubl_cii`` — importación y exportación UBL/CII.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/__init__.py``
(``odoo-tools@622ddc2a``, LGPL-3) — atribución y aviso de licencia preservados
(DEC-KX-03).

Sin imports de modelos: los declara ``models/__init__.py``, que Django carga al
levantar la app; las extensiones sobre modelos ajenos las aplica
``AccountEdiUblCiiConfig.ready()``. Misma plantilla que ``addons/utm/__init__.py``.

``uninstall_hook`` — no se porta, y por qué
============================================

La fuente declara aquí un ``uninstall_hook`` que llama a
``env['res.partner']._clear_removed_edi_formats('facturx', 'nlcius',
'ubl_a_nz', 'ubl_bis3', 'ubl_sg', 'xrechnung')`` para limpiar el campo
``invoice_edi_format`` de los contactos al desinstalar el módulo.

Dos piezas ausentes, medidas:

* ``ResPartner._clear_removed_edi_formats`` → **0 hits** en el árbol;
* este árbol **no tiene el mecanismo** ``uninstall_hook`` del manifiesto: el
  cargador (``src/modules/module_graph.py``) lee ``depends``, ``auto_install``
  e ``installable``, no ganchos de ciclo de vida. Mismo desenlace, y misma
  redacción, que ``addons/sale_timesheet/__manifest__.py:67`` ya declaró para
  su ``post_init_hook``/``uninstall_hook``.

Desenlace: **bloqueado por dos piezas nombradas**, ninguna en el write-set de
este pase. Sucesor: portar el ciclo de vida de instalación de módulos.
"""
