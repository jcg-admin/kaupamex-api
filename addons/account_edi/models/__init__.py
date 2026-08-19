"""Modelos del addon ``account_edi`` (estructura Odoo: un archivo por modelo).

Sólo los DOS modelos Django concretos (``AccountEdiFormat``,
``AccountEdiDocument``) — necesarios para que Django los descubra al
migrar. Los archivos que sólo EXTIENDEN modelos de otro addon
(``account_journal.py``, ``account_move.py``, ``account_move_send.py``,
``ir_attachment.py``, ``ir_actions_report.py``) NO se importan aquí: se
cargan desde ``AccountEdiConfig.ready()``, cuando el registro de modelos ya
está poblado — mismo criterio que ``account/models/__init__.py``.
"""
from .account_edi_document import AccountEdiDocument
from .account_edi_format import AccountEdiFormat

__all__ = ['AccountEdiFormat', 'AccountEdiDocument']
