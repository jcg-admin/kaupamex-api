"""Modelos del addon ``account_edi_proxy_client`` (estructura Odoo: un
archivo por modelo).

Sólo el modelo Django concreto (``AccountEdiProxyUser``) — necesario para
que Django lo descubra al migrar. ``account_edi_proxy_auth.py``
(``OdooEdiProxyAuth``, clase Python plana, no modelo) se importa donde se
usa (``account_edi_proxy_user.py``), no aquí. Los archivos que sólo
EXTIENDEN modelos de otro addon (``key.py``, ``res_company.py``) NO se
importan aquí: se cargan desde ``AccountEdiProxyClientConfig.ready()``,
mismo criterio que ``account_edi/models/__init__.py``.
"""
from .account_edi_proxy_user import AccountEdiProxyError, AccountEdiProxyUser

__all__ = ['AccountEdiProxyError', 'AccountEdiProxyUser']
