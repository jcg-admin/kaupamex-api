# Adaptado de Odoo `account_peppol/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Peppol',
    'summary': 'This module is used to send/receive documents with PEPPOL',
    'description': """
- Register as a PEPPOL participant
- Send and receive documents via PEPPOL network in Peppol BIS Billing 3.0 format
    """,
    'category': 'Accounting/Accounting',
    'version': '1.2',
    # Los 21 países de la red, verbatim de la referencia. Su comentario también:
    # !!! KEEP ALIGNED WITH ACCOUNT/MODELS/COMPANY.PEPPOL_DEFAULT_COUNTRIES
    # (esa constante NO está en este árbol — medido, 0 hits; ver
    # `models/account_move_send.py`).
    'countries': [
        'at', 'be', 'ch', 'cy', 'cz', 'de', 'dk', 'ee', 'es', 'fi',
        'fr', 'ie', 'is', 'lt', 'lu', 'lv', 'mt', 'nl', 'no', 'se',
        'si',
    ],
    # `depends` MEDIDO contra los imports reales de este addon:
    # - account_edi_proxy_client → AccountEdiProxyUser y AccountEdiProxyError,
    #   el transporte sobre el que se monta todo (models/account_edi_proxy_user.py).
    # - account → AccountMove y AccountJournal, destinos de extensión.
    # - base   → ResCompany, ResPartner y SystemParameter (import de Python).
    #
    # DIVERGE de la referencia, que declara ['account_edi_proxy_client',
    # 'account_edi_ubl_cii']:
    # - `account_edi_ubl_cii` NO se declara: se está portando en otro pase, en
    #   paralelo, y este addon no lo importa. Cada símbolo que lo necesita está
    #   marcado *BLOQUEADO por account_edi_ubl_cii* en el docstring de su
    #   archivo; el orquestador reconcilia la arista al consolidar.
    # - `account` y `base` se declaran explícitos porque el import es de Python
    #   (la referencia los recibe por transitividad), mismo criterio que
    #   `account_debit_note` con `base`.
    'depends': [
        'base',
        'account',
        'account_edi_proxy_client',
    ],
    # `external_dependencies` de la referencia: {'python': ['phonenumbers']}.
    # MEDIDO: `grep -ci phonenumbers uv.lock` → 0. No se declara porque no se
    # instala: el addon la importa con try/except, igual que la fuente, y
    # `_check_phonenumbers_import` levanta el error legible que la propia
    # referencia define para ese caso.
    # `python-stdnum` (que la referencia usa en res_company.py sin declararlo
    # aquí) tampoco está: 0 hits. Ver `models/res_company.py`.
    #
    # `data` (11 XML) y `demo` (1) no se portan: capa de datos y cliente web de
    # Odoo. `post_init_hook` declarado y no portado — ver `__init__.py`.
    'installable': True,
    'application': False,
    # La referencia declara `auto_install: ['account_edi_ubl_cii']`. Aquí no:
    # ese addon no está en `depends` (ver arriba), así que un auto-install
    # anclado a él no tendría anclaje.
    'auto_install': False,
    'author': 'Odoo S.A.',
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
}
