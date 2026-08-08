# Adaptado de Odoo `account_qr_code_emv/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2a, odoo19c:) — atribución y aviso de licencia
# preservados (DEC-KX-03).
{
    'name': 'Puente QR EMV Merchant-Presented',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Vocabulario EMV (proxy, referencia, CRC16) sobre '
               'res.partner.bank, para que localizaciones concretas '
               'activen su propio método de QR de pago.',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia (que declara sólo `account`, porque su `_get_qr_vals`
    # sobreescribe el mecanismo que `account/models/res_partner_bank.py`
    # define — con `super()` real, vía `_inherit`). Ese archivo no existe
    # todavía en este árbol (medido: `find src/addons/account -iname
    # "*partner_bank*"` da 0), así que este puente no importa nada de
    # `account` — sólo `base.ResPartnerBank`. Ver la sección "Divergencias
    # declaradas" en `models/res_bank.py` para el DESCONOCIDO que esto abre.
    'depends': [
        'base',      # ResPartnerBank
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_qr_code_emv` en Odoo
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
