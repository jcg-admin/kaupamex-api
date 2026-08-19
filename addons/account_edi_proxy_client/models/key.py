r"""``certificate.key`` — lo que ``account_edi_proxy_client`` le cuelga
(≙ ``_inherit``).

Adaptación de ``odoo19c: account_edi_proxy_client/models/key.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 12 líneas)
— atribución y aviso de licencia preservados (DEC-KX-03).

Un símbolo, portado
========================

``_account_edi_fernet_decrypt`` — descifra los datos que llegan del proxy
(cifrados con una llave simétrica Fernet, que a su vez llega cifrada con la
llave asimétrica del usuario — ver ``_decrypt_data`` en
``account_edi_proxy_user.py``).

Dependencia medida — ``cryptography`` SÍ disponible (regla 1 de la tanda)
================================================================================

.. code-block:: text

   grep -ic cryptography uv.lock
   → 48

[PROVEN]. A diferencia de ``werkzeug`` (0 hits, ver
``account_edi_proxy_auth.py``), ``cryptography`` está declarado — de hecho
``certificate/models/key.py`` (este mismo árbol) ya lo usa para RSA/EC/
Ed25519. ``cryptography.fernet.Fernet`` es el mismo paquete, otro
submódulo — se importa sin sustitución.
"""
from cryptography.fernet import Fernet

from addons.certificate.models.key import CertificateKey
from orm.method_chain import chain_method


def _account_edi_fernet_decrypt(cls, key, message):
    """≙ ``_account_edi_fernet_decrypt`` (``odoo19c: :7-9``)."""
    fernet_key = Fernet(key)
    return fernet_key.decrypt(message)


def apply_account_edi_proxy_client_extensions():
    """≙ ``_inherit = 'certificate.key'`` de ``account_edi_proxy_client``.

    Nuevo — sin contraparte previa en ``CertificateKey`` (medido: ``grep -n
    "_account_edi_fernet_decrypt" addons/certificate/models/key.py`` → 0
    hits), así que ``chain_method`` lo instala tal cual.
    """
    chain_method(CertificateKey, '_account_edi_fernet_decrypt',
                 classmethod(_account_edi_fernet_decrypt))
