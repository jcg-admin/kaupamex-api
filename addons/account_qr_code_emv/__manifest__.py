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
    # `depends` MEDIDO — y CORREGIDO el 2026-08-14 (#320, :ref:`h-api-564`).
    #
    # Decía `['base']` con esta medición: "el puente no importa nada de
    # `account`, sólo `base.ResPartnerBank`; `account/models/res_partner_bank.py`
    # no existe todavía en este árbol". La primera mitad seguía siendo cierta
    # —no hay `import` de `account` aquí—; la segunda quedó obsoleta sin que
    # nadie tocara este archivo: `account/models/res_partner_bank.py` SÍ existe
    # ya, y es quien instala el TERMINAL de la cadena sobre
    # `base.ResPartnerBank` (`:227-252`, vía `chain_method`).
    #
    # La consecuencia es de ORDEN DE CARGA, que es justo lo que un `depends`
    # declara. `chain_method` deja fuera al último que instala: si este addon
    # corre ANTES que `account`, el terminal de `account`
    # (`_get_qr_code_generation_params` → `NotImplementedError`,
    # `_get_available_qr_methods` → `[]`) queda por encima y sepulta el eslabón
    # EMV. Con la lista escrita a mano el orden lo sostenía un comentario en
    # `base.py`; al derivarla del grafo (#320) este addon subió a profundidad 0
    # y los dos tests del puente cayeron:
    #
    #   assert 'emv_qr' in {'sct_qr': ('SEPA Credit Transfer QR', 20)}
    #   addons/account/models/res_partner_bank.py:157: NotImplementedError
    #
    # La métrica vieja —imports de módulo— es CIEGA a de quién es el método
    # que se encadena. La referencia lo tenía bien desde el principio:
    # `odoo19c: account_qr_code_emv/__manifest__.py` declara `['account']`.
    'depends': [
        'account',   # dueño del terminal de la cadena de QR (res_partner_bank)
        'base',      # ResPartnerBank — la clase que ambos extienden
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_qr_code_emv` en Odoo
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
