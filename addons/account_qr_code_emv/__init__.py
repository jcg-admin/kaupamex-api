"""``account_qr_code_emv`` — puente para códigos QR EMV Merchant-Presented.

Adaptación de Odoo ``account_qr_code_emv`` (``odoo-tools@622ddc2a``,
``odoo19c:``, licencia ``LGPL-3`` declarada en su ``__manifest__.py``) —
atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: un módulo puente ("bridge module" en su propia descripción) que
cuelga de ``res.partner.bank`` el vocabulario EMV (proxy, referencia,
categoría de comercio, serialización TLV, CRC16) sin resolver ningún país en
concreto. Cada localización real (``l10n_br``, ``l10n_hk``, ``l10n_kh``,
``l10n_sg``, ``l10n_th``, ``l10n_vn`` en ``odoo19c:``, ninguna presente en
este árbol todavía) sobreescribe ``_get_merchant_account_info``,
``_get_additional_data_field`` y los dos ``_compute_*`` para activar su
propio método de pago.

Qué NO trae este puente por sí solo: sin una localización que lo active,
``emv_qr`` queda registrado en ``_get_available_qr_methods`` pero nunca
elegible (``_get_error_messages_for_qr`` lo rechaza siempre) — mismo
comportamiento que la referencia.
"""
