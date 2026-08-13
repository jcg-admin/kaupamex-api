# Adaptado de Odoo `account_qr_code_sepa/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Código QR de transferencia SEPA',
    'version': '1.0',
    'category': 'Accounting/Payment',
    'summary': 'Genera los valores del código QR de transferencia SEPA '
               '(SCT, formato EPC) para una cuenta res.partner.bank.',
    # `depends` alineado con la referencia, que declara `['account',
    # 'base_iban']`. Hasta 2026-08-13 este campo declaraba sólo `base` porque
    # ninguno de los dos existía en el árbol; los dos existen ya y la
    # afirmación quedó falsa (medido: `find src/addons -maxdepth 1 -iname
    # "base_iban"` → `src/addons/base_iban`; `find src/addons/account -iname
    # "*partner_bank*"` → `models/res_partner_bank.py`, api@94bc01e).
    #
    # Las dos dependencias son de ORDEN, no de import: los tres addons cuelgan
    # funciones sobre la MISMA `base.ResPartnerBank` con `chain_method`, así
    # que quien va antes queda debajo en la cadena. `account` instala los
    # terminales del bloque QR (`_get_qr_vals` → NotImplementedError,
    # `_get_error_messages_for_qr` → None) sobre los que este addon encadena;
    # `base_iban` deriva `acc_type='iban'`, sin lo cual el segundo check de
    # `_get_error_messages_for_qr` rechaza TODA cuenta y el addon queda muerto
    # — que es exactamente el estado que tuvo hasta que `base_iban` se portó.
    #
    # Este addon sigue vendorizando localmente (`tools.py`) el validador de
    # referencia estructurada que en la referencia vive en `account/tools/
    # structured_reference.py` — ver "Divergencias declaradas" en
    # `models/res_bank.py`.
    'depends': [
        'base',        # ResPartnerBank, ResPartner, ResBank
        'account',     # terminales del bloque QR sobre res.partner.bank
        'base_iban',   # deriva acc_type='iban' (el segundo check lo exige)
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_qr_code_sepa` en Odoo
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # `True`, fiel a la referencia: este puente se instala solo cuando sus dos
    # lados (`account` y `base_iban`) ya están. El comentario anterior decía
    # que "este ORM no tiene ese mecanismo" y era falso — `ModuleGraph.
    # auto_installable` (`src/modules/module_graph.py:141`) porta el algoritmo
    # de punto fijo de `odoo19c: odoo/modules/db.py:91-124`, y dos manifests
    # del árbol ya declaran el campo (`authz_totp_mail`, `authz_passkey`).
    #
    # Lo que sigue faltando es su CONSUMIDOR: `auto_installable()` no se llama
    # desde ningún camino de instalación (medido: 0 llamadas fuera de su
    # propia definición y de dos docstrings), porque la instalación real es
    # `INSTALLED_APPS` explícito. Declararlo aquí es correcto y hoy inerte;
    # el hueco está registrado en H-API-410.
    'auto_install': True,
}
