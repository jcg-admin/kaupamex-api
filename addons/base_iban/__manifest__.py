# Adaptado de Odoo `base_iban/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Cuentas bancarias IBAN',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Valida el checksum mod-97 del IBAN, deriva el BBAN y sus '
               'tramos por país, y marca la cuenta como acc_type=iban.',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia (que declara `['account', 'web']`). Este addon sólo
    # importa `base.ResPartnerBank` para colgarle sus métodos; `web` es el
    # paquete de assets del cliente JS de Odoo (el widget de entrada IBAN),
    # sin equivalente en un backend DRF. `account` lo necesita la referencia
    # porque su `_get_supported_account_types` vive allí; aquí el terminal
    # está en `base` (`res_partner_bank.py`), así que no hace falta.
    'depends': [
        'base',      # ResPartnerBank — el modelo que este addon extiende
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `base_iban` en Odoo es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La referencia no declara `auto_install`; se deja explícito en False por
    # el mismo criterio que `account_qr_code_sepa`: aquí la instalación es
    # `INSTALLED_APPS`, no hay mecanismo de auto-instalación por dependencias.
    'auto_install': False,
}
