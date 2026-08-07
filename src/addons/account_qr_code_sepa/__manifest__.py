# Adaptado de Odoo `account_qr_code_sepa/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Código QR de transferencia SEPA',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Genera los valores del código QR de transferencia SEPA '
               '(SCT, formato EPC) para una cuenta res.partner.bank.',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia (que declara `['account', 'base_iban']`, porque su
    # `_get_qr_vals` sobreescribe `account/models/res_partner_bank.py` con
    # `super()` real vía `_inherit`, y usa `base_iban` para detectar cuentas
    # IBAN). Ninguno de los dos existe todavía en este árbol (medido: `find
    # src/addons/account -iname "*partner_bank*"` da 0; `find src/addons
    # -maxdepth 1 -iname "base_iban"` da 0) — mismo hallazgo que
    # `account_qr_code_emv/__manifest__.py` ya documentó para su propio
    # puente. Este addon sólo importa `base.ResPartnerBank` (para colgarle el
    # método) y vendoriza localmente (`tools.py`) el validador de referencia
    # estructurada que en la referencia vive en `account/tools/
    # structured_reference.py` — ver la sección "Divergencias declaradas" en
    # `models/res_bank.py`.
    'depends': [
        'base',      # ResPartnerBank, ResPartner, ResBank
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_qr_code_sepa` en Odoo
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La referencia declara `auto_install: True` (se instala solo cuando
    # `account` y `base_iban` ya lo están). Este ORM no tiene ese mecanismo —
    # la instalación es `INSTALLED_APPS` explícito (`config/settings/
    # base.py`, fuera de este alcance) — así que se deja en `False`, mismo
    # criterio que `account_qr_code_emv/__manifest__.py` ya fijó para el
    # mismo campo sin mecanismo real detrás.
    'auto_install': False,
}
