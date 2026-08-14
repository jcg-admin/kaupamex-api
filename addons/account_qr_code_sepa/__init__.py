"""``account_qr_code_sepa`` — código QR de transferencia SEPA (SCT) en cuentas.

Adaptación de Odoo ``account_qr_code_sepa`` (``odoo-tools@622ddc2aa5563d12
295b4ab7d3eb438a43eb31de``, ``odoo19c:``, licencia ``LGPL-3`` declarada en su
``__manifest__.py``) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: un puente ("bridge module", igual que ``account_qr_code_emv``) que
cuelga de ``res.partner.bank`` el método de generación de códigos QR de
transferencia SEPA Credit Transfer (``sct_qr``) — el estándar del European
Payments Council para pagar por transferencia bancaria escaneando un QR.

Qué NO trae: no genera el propio código de barras/imagen (eso es
``_get_qr_code_url``/``_get_qr_code_base64`` en ``account/models/
res_partner_bank.py``, no portado aún — ver "Divergencias declaradas" en
``models/res_bank.py``) — sólo los valores y parámetros que ese generador
consumiría.
"""
