"""``base_iban`` — validación y formato de cuentas IBAN sobre ``res.partner.bank``.

Adaptación de Odoo ``base_iban`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438
a43eb31de``, ``odoo19c:``, licencia ``LGPL-3`` declarada en su
``__manifest__.py``) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: un puente que enseña a ``res.partner.bank`` a reconocer el
International Bank Account Number — el checksum mod-97 de la norma ISO 13616 y
la plantilla por país que dice qué tramo del número es banco, sucursal o
cuenta. Con él, ``acc_type`` pasa de ``bank`` a ``iban`` cuando el número
valida, y el número se guarda en grupos de cuatro caracteres.

Relación con ``base_bank``: aquél implementa el **mismo patrón** (dispatcher de
validación por país) para la CLABE mexicana, y su docstring ya declaraba a
``base_iban`` como su fuente. No se solapan — son dos países en el mismo
mecanismo, y desde hoy los dos encadenan sobre ``retrieve_acc_type``.
"""
