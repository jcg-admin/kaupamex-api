# Adaptado de Odoo Community `account_edi_proxy_client/__manifest__.py`
# (LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Proxy features for account_edi',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'account_edi_proxy_client.user — cliente genérico del proxy de '
        'Odoo S.A. (Access Point) que registra y autentica usuarios de un '
        'formato EDI concreto'
    ),
    # `depends` MEDIDO contra los imports reales de los modelos de este
    # addon — DIVERGE de la referencia, con razón declarada. La referencia
    # declara `['account', 'certificate']`; aquí se añade `account_edi`
    # porque `account_edi_proxy_user.py::_renew_token` reutiliza
    # `lock_for_update()` (``account_edi/models/account_edi_document.py``)
    # en vez de duplicar la primitiva ``SELECT FOR UPDATE NOWAIT`` +
    # traducción a ``LockError`` — un mecanismo CONSTRUIDO una sola vez,
    # no repetido por archivo (mismo criterio de no-duplicación que
    # ``porte-completo-no-parcial.md`` aplica a símbolos, aquí aplicado a
    # un helper interno).
    'depends': [
        'account',      # transitivo, vía account_edi
        'account_edi',  # lock_for_update() reutilizado, no duplicado
        'certificate',  # CertificateKey._sign/_decrypt/_generate_rsa_private_key
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_edi_proxy_client`
    # en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
    # 'post_init_hook': '_create_demo_config_param' de la referencia —
    # BLOQUEADO, sin mecanismo de hook post-instalación en este stack (ver
    # __init__.py). No se declara la clave: no hay función que apuntara.
}
